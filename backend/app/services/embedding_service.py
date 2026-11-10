"""CampusMind AI - Embedding Service.

Generates dense vector embeddings using the configured sentence-transformer model.

Responsibilities:
Class EmbeddingService:
1. EmbeddingService.__init__(): Initializes the service and loads the embedding model.
2. EmbeddingService._ensure_model_loaded(): Loads model and tokenizer into class-level singleton cache.
3. EmbeddingService.model(): Provides access to the underlying SentenceTransformer model.
4. EmbeddingService.tokenizer(): Provides access to the HuggingFace tokenizer.
5. EmbeddingService.count_tokens(): Returns exact token count of text using the model tokenizer.
6. EmbeddingService._validate_input_length(): Checks that text does not exceed sequence length limit.
7. EmbeddingService.embed_text(): Computes normalized 384-dimensional embedding for a single text.
8. EmbeddingService.embed_query(): Encodes search queries into dense vector representations.
9. EmbeddingService.embed_chunks(): Batches and generates embeddings across multiple document chunks.
"""

import logging
from typing import List, Union, Optional
import numpy as np

from app.schemas.chunk import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)

# Model constants
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EXPECTED_DIMENSION = 384
MAX_SEQUENCE_LENGTH = 512


# Raised when an input sequence exceeds the model's maximum sequence length (512 tokens).
class InputSequenceTooLongError(ValueError):
    pass


# Generates dense vector embeddings using the configured sentence-transformer model.
class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model = None
    _tokenizer = None

    # Initializes the EmbeddingService with model name, batch size, and limits.
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        batch_size: int = 32,
        max_sequence_length: int = MAX_SEQUENCE_LENGTH,
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_sequence_length = max_sequence_length
        self.device = device
        self._ensure_model_loaded()

    # Loads the SentenceTransformer model and tokenizer once into class-level cache.
    def _ensure_model_loaded(self):
        if EmbeddingService._model is None:
            logger.info("Loading embedding model %s on device: %s...", self.model_name, self.device)
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(self.model_name, device=self.device)
            # Ensure model max seq length is set to 512
            model.max_seq_length = self.max_sequence_length
            EmbeddingService._model = model
            EmbeddingService._tokenizer = model.tokenizer
            logger.info("Embedding model %s successfully loaded.", self.model_name)

    # Returns the loaded SentenceTransformer model instance.
    @property
    def model(self):
        return EmbeddingService._model

    # Returns the underlying HuggingFace tokenizer instance.
    @property
    def tokenizer(self):
        return EmbeddingService._tokenizer

    # Calculates exact token count using the model's actual HuggingFace tokenizer.
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        tokens = self.tokenizer.encode(text, add_special_tokens=True)
        return len(tokens)

    # Validates that input does not exceed max_sequence_length tokens.
    def _validate_input_length(self, text: str, identifier: str = "text"):
        token_count = self.count_tokens(text)
        if token_count > self.max_sequence_length:
            raise InputSequenceTooLongError(
                f"Input '{identifier}' has {token_count} tokens, which exceeds the model limit of "
                f"{self.max_sequence_length} tokens. Re-chunk the input before embedding."
            )

    # Generates a 384-dimensional normalized vector for a single piece of text.
    def embed_text(self, text: str) -> List[float]:
        if not isinstance(text, str):
            raise TypeError(f"Expected text to be a string, got {type(text)}")
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Cannot generate embedding for empty or whitespace-only text.")

        self._validate_input_length(cleaned, identifier="text")

        vector = self.model.encode(
            cleaned,
            normalize_embeddings=True,
            show_progress_bar=False,
            device=self.device,
        )
        vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)

        if len(vector_list) != EXPECTED_DIMENSION:
            raise RuntimeError(
                f"Unexpected vector dimension: expected {EXPECTED_DIMENSION}, got {len(vector_list)}"
            )

        return vector_list

    # Generates a 384-dimensional normalized vector for a user search query.
    def embed_query(self, query: str) -> List[float]:
        if not isinstance(query, str):
            raise TypeError(f"Expected query to be a string, got {type(query)}")
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty or whitespace-only.")

        self._validate_input_length(cleaned, identifier="query")

        # BGE models use standard sentence encoding for queries
        return self.embed_text(cleaned)

    # Generates embeddings for a batch of Chunk objects, preserving complete metadata.
    def embed_chunks(
        self,
        chunks: List[Chunk],
        batch_size: Optional[int] = None,
    ) -> List[EmbeddedChunk]:
        if not isinstance(chunks, list):
            raise TypeError(f"Expected chunks to be a list, got {type(chunks)}")

        if not chunks:
            return []

        effective_batch_size = batch_size or self.batch_size
        if effective_batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {effective_batch_size}")

        texts_to_embed = []
        for idx, chunk in enumerate(chunks):
            if not isinstance(chunk, Chunk):
                raise TypeError(f"Item at index {idx} is not a Chunk instance, got {type(chunk)}")
            content = chunk.content.strip()
            if not content:
                raise ValueError(f"Chunk at index {idx} (ID: {chunk.metadata.chunk_id}) contains empty text.")
            self._validate_input_length(content, identifier=f"chunk_{idx}")
            texts_to_embed.append(content)

        # Batch inference with SentenceTransformer
        raw_vectors = self.model.encode(
            texts_to_embed,
            batch_size=effective_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            device=self.device,
        )

        embedded_chunks: List[EmbeddedChunk] = []
        for chunk, vec in zip(chunks, raw_vectors):
            vec_list = vec.tolist() if hasattr(vec, "tolist") else list(vec)
            if len(vec_list) != EXPECTED_DIMENSION:
                raise RuntimeError(
                    f"Unexpected vector dimension: expected {EXPECTED_DIMENSION}, got {len(vec_list)}"
                )
            embedded_chunks.append(EmbeddedChunk(chunk=chunk, embedding=vec_list))

        return embedded_chunks

