"""CampusMind AI - Embedding Service.

Generates dense vector embeddings using the configured sentence-transformer model.
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


class InputSequenceTooLongError(ValueError):
    """Raised when an input sequence exceeds the model's maximum sequence length (512 tokens)."""
    pass


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model = None
    _tokenizer = None

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        batch_size: int = 32,
        max_sequence_length: int = MAX_SEQUENCE_LENGTH,
        device: str = "cpu",
    ):
        """
        Initializes the EmbeddingService.
        
        Args:
            model_name: Name or path of the SentenceTransformer model (defaults to BAAI/bge-small-en-v1.5).
            batch_size: Default batch size for multi-chunk embedding.
            max_sequence_length: Maximum allowed sequence tokens (512 for BGE-small).
            device: Device to run embeddings on ('cpu').
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_sequence_length = max_sequence_length
        self.device = device
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """Ensures the SentenceTransformer model and its underlying tokenizer are loaded once."""
        if EmbeddingService._model is None:
            logger.info("Loading embedding model %s on device: %s...", self.model_name, self.device)
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(self.model_name, device=self.device)
            # Ensure model max seq length is set to 512
            model.max_seq_length = self.max_sequence_length
            EmbeddingService._model = model
            EmbeddingService._tokenizer = model.tokenizer
            logger.info("Embedding model %s successfully loaded.", self.model_name)

    @property
    def model(self):
        return EmbeddingService._model

    @property
    def tokenizer(self):
        return EmbeddingService._tokenizer

    def count_tokens(self, text: str) -> int:
        """
        Calculates exact token count using the model's actual HuggingFace tokenizer.
        """
        if not text:
            return 0
        tokens = self.tokenizer.encode(text, add_special_tokens=True)
        return len(tokens)

    def _validate_input_length(self, text: str, identifier: str = "text"):
        """
        Validates that input does not exceed max_sequence_length tokens.
        Raises InputSequenceTooLongError rather than silently allowing unintended truncation.
        """
        token_count = self.count_tokens(text)
        if token_count > self.max_sequence_length:
            raise InputSequenceTooLongError(
                f"Input '{identifier}' has {token_count} tokens, which exceeds the model limit of "
                f"{self.max_sequence_length} tokens. Re-chunk the input before embedding."
            )

    def embed_text(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional normalized vector for a single piece of text.
        
        Args:
            text: Non-empty input string.
            
        Returns:
            List of 384 floats.
        """
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

    def embed_query(self, query: str) -> List[float]:
        """
        Generates a 384-dimensional normalized vector for a user search query.
        Uses the exact same embedding model configuration as document chunks.
        
        Args:
            query: Non-empty query string.
            
        Returns:
            List of 384 floats.
        """
        if not isinstance(query, str):
            raise TypeError(f"Expected query to be a string, got {type(query)}")
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty or whitespace-only.")

        self._validate_input_length(cleaned, identifier="query")

        # BGE models use standard sentence encoding for queries
        return self.embed_text(cleaned)

    def embed_chunks(
        self,
        chunks: List[Chunk],
        batch_size: Optional[int] = None,
    ) -> List[EmbeddedChunk]:
        """
        Generates embeddings for a batch of Chunk objects, preserving complete metadata
        and pairing each embedding with its corresponding chunk.
        
        Args:
            chunks: List of Chunk objects to embed.
            batch_size: Optional custom batch size (overrides default).
            
        Returns:
            List[EmbeddedChunk] with 1-to-1 association.
        """
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

