"""CampusMind AI - Chunking Service.

Provides fixed, recursive, and semantic text chunking with provenance metadata.

Responsibilities:
1. approximate_tokens_from_words(): Estimates token counts from whitespace-separated words.
2. split_into_sentences(): Divides raw text into distinct grammatical sentences.
3. cosine_similarity(): Computes dot-product similarity between two 1D vectors.
Class ChunkingService:
4. ChunkingService.__init__(): Initializes default token sizes, overlaps, and thresholds.
5. ChunkingService.embedding_service(): Returns the assigned or lazily created EmbeddingService.
6. ChunkingService._validate_config(): Validates that chunk size and overlap values are positive and consistent.
7. ChunkingService._prepare_pages(): Converts varied document inputs into standardized ExtractedPage lists.
8. ChunkingService.recursive_chunking(): Chunks text recursively using separators and tokenizer lengths.
9. ChunkingService.fixed_chunking(): Performs sliding-window fixed token chunking with overlap.
10. ChunkingService.semantic_chunking(): Groups sentences into chunks based on semantic similarity transitions.
11. ChunkingService.chunk_document(): Dispatches chunking tasks to the chosen strategy.
"""

import re
import uuid
import logging
from typing import List, Optional, Union, Callable, Literal, Sequence
import numpy as np

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.schemas.chunk import Chunk, ChunkMetadata, ExtractedPage, ExtractedDocument
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

ChunkingMethodType = Literal["fixed", "recursive", "semantic"]


# Computes an approximate token count based on whitespace-separated words.
def approximate_tokens_from_words(text: str) -> int:
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.33))


# Splits text into constituent sentences using punctuation boundaries (.
def split_into_sentences(text: str) -> List[str]:
    if not text or not text.strip():
        return []
    # Match sentences ending with . ! or ? followed by whitespace or end of string
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences


# Computes cosine similarity between two 1D vectors.
def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# Unified chunking service supporting Fixed, Recursive, and Semantic chunking.
class ChunkingService:

    # Initializes the ChunkingService.
    def __init__(
        self,
        default_chunk_size_tokens: int = 400,
        default_chunk_overlap_tokens: int = 50,
        chars_per_token_estimate: float = 4.0,
        embedding_service: Optional[EmbeddingService] = None,
        default_similarity_threshold: float = 0.65,
    ):
        self.default_chunk_size_tokens = default_chunk_size_tokens
        self.default_chunk_overlap_tokens = default_chunk_overlap_tokens
        self.chars_per_token_estimate = chars_per_token_estimate
        self._embedding_service = embedding_service
        self.default_similarity_threshold = default_similarity_threshold

    @property
    # Lazy-instantiates or returns the embedding service.
    def embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    # Validates chunk sizing and overlap parameters.
    def _validate_config(self, chunk_size: int, chunk_overlap: int):
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly smaller than chunk_size ({chunk_size})"
            )

    # Normalizes input into a list of ExtractedPage objects.
    def _prepare_pages(
        self,
        document_or_text: Union[str, ExtractedDocument, List[ExtractedPage]],
    ) -> List[ExtractedPage]:
        if isinstance(document_or_text, ExtractedDocument):
            return document_or_text.pages
        elif isinstance(document_or_text, list):
            return document_or_text
        elif isinstance(document_or_text, str):
            if not document_or_text.strip():
                return []
            return [ExtractedPage(page_number=1, text=document_or_text)]
        else:
            raise TypeError(f"Unsupported document type: {type(document_or_text)}")

    # -------------------------------------------------------------------------
    # 1. Recursive Chunking
    # -------------------------------------------------------------------------
    def recursive_chunking(
        self,
        document: Union[str, ExtractedDocument, List[ExtractedPage]],
        document_id: str = "doc_default",
        document_name: str = "document",
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
        separators: Optional[List[str]] = None,
        length_function: Optional[Callable[[str], int]] = None,
    ) -> List[Chunk]:
        target_tokens = (
            self.default_chunk_size_tokens
            if chunk_size_tokens is None
            else chunk_size_tokens
        )
        target_overlap = (
            self.default_chunk_overlap_tokens
            if chunk_overlap_tokens is None
            else chunk_overlap_tokens
        )

        self._validate_config(target_tokens, target_overlap)

        if isinstance(document, ExtractedDocument):
            document_id = document.document_id
            document_name = document.document_name

        pages = self._prepare_pages(document)
        if not pages:
            return []

        # Use tokenizer token counting when embedding_service is available, or fallback to word-based approximation
        if length_function is not None:
            token_len_func = length_function
        elif self._embedding_service is not None:
            token_len_func = self._embedding_service.count_tokens
        else:
            token_len_func = approximate_tokens_from_words

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=target_tokens,
            chunk_overlap=target_overlap,
            length_function=token_len_func,
            separators=separators or ["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

        chunks: List[Chunk] = []
        global_chunk_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            raw_splits = splitter.split_text(text)
            for split_text in raw_splits:
                cleaned = split_text.strip()
                if not cleaned:
                    continue

                token_count = token_len_func(cleaned)
                meta = ChunkMetadata(
                    documentId=document_id,
                    documentName=document_name,
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=global_chunk_idx,
                    chunkingMethod="recursive",
                    pageNumber=page.page_number,
                    tokenCountApprox=token_count,
                    characterCount=len(cleaned),
                )
                chunks.append(Chunk(content=cleaned, metadata=meta))
                global_chunk_idx += 1

        return chunks

    # -------------------------------------------------------------------------
    # 2. Fixed-Size Chunking
    # -------------------------------------------------------------------------
    def fixed_chunking(
        self,
        document: Union[str, ExtractedDocument, List[ExtractedPage]],
        document_id: str = "doc_default",
        document_name: str = "document",
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
    ) -> List[Chunk]:
        target_tokens = (
            self.default_chunk_size_tokens
            if chunk_size_tokens is None
            else chunk_size_tokens
        )
        target_overlap = (
            self.default_chunk_overlap_tokens
            if chunk_overlap_tokens is None
            else chunk_overlap_tokens
        )

        self._validate_config(target_tokens, target_overlap)

        if isinstance(document, ExtractedDocument):
            document_id = document.document_id
            document_name = document.document_name

        pages = self._prepare_pages(document)
        if not pages:
            return []

        # Convert token window to approximate word window (1 word ~ 1.33 tokens -> words = tokens / 1.33)
        # Using words ensures we don't break mid-word.
        words_per_chunk = max(1, int(target_tokens / 1.33))
        words_overlap = int(target_overlap / 1.33) if target_overlap > 0 else 0
        step_size = max(1, words_per_chunk - words_overlap)

        chunks: List[Chunk] = []
        global_chunk_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            words = text.split()
            if not words:
                continue

            num_words = len(words)
            start_idx = 0

            while start_idx < num_words:
                end_idx = min(start_idx + words_per_chunk, num_words)
                chunk_words = words[start_idx:end_idx]
                chunk_text = " ".join(chunk_words)

                token_count = approximate_tokens_from_words(chunk_text)
                meta = ChunkMetadata(
                    documentId=document_id,
                    documentName=document_name,
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=global_chunk_idx,
                    chunkingMethod="fixed",
                    pageNumber=page.page_number,
                    tokenCountApprox=token_count,
                    characterCount=len(chunk_text),
                )
                chunks.append(Chunk(content=chunk_text, metadata=meta))
                global_chunk_idx += 1

                if end_idx >= num_words:
                    break
                start_idx += step_size

        return chunks

    # -------------------------------------------------------------------------
    # 3. Genuine Semantic Chunking
    # -------------------------------------------------------------------------
    def semantic_chunking(
        self,
        document: Union[str, ExtractedDocument, List[ExtractedPage]],
        document_id: str = "doc_default",
        document_name: str = "document",
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> List[Chunk]:
        target_tokens = (
            self.default_chunk_size_tokens
            if chunk_size_tokens is None
            else chunk_size_tokens
        )
        target_overlap = (
            self.default_chunk_overlap_tokens
            if chunk_overlap_tokens is None
            else chunk_overlap_tokens
        )
        threshold = (
            self.default_similarity_threshold
            if similarity_threshold is None
            else similarity_threshold
        )

        self._validate_config(target_tokens, target_overlap)
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"similarity_threshold must be between 0.0 and 1.0, got {threshold}")

        if isinstance(document, ExtractedDocument):
            document_id = document.document_id
            document_name = document.document_name

        pages = self._prepare_pages(document)
        if not pages:
            return []

        chunks: List[Chunk] = []
        global_chunk_idx = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            sentences = split_into_sentences(text)
            if not sentences:
                continue

            # If document has only 1 or 2 sentences, return directly as a chunk
            if len(sentences) <= 2:
                chunk_text = " ".join(sentences)
                token_count = approximate_tokens_from_words(chunk_text)
                meta = ChunkMetadata(
                    documentId=document_id,
                    documentName=document_name,
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=global_chunk_idx,
                    chunkingMethod="semantic",
                    pageNumber=page.page_number,
                    tokenCountApprox=token_count,
                    characterCount=len(chunk_text),
                )
                chunks.append(Chunk(content=chunk_text, metadata=meta))
                global_chunk_idx += 1
                continue

            # Compute embeddings for each sentence in batch
            embeddings = [self.embedding_service.embed_text(s) for s in sentences]

            # Calculate cosine similarities between adjacent sentences
            similarities: List[float] = []
            for i in range(len(sentences) - 1):
                sim = cosine_similarity(embeddings[i], embeddings[i + 1])
                similarities.append(sim)

            # Build semantic segments
            # A split occurs if:
            # - similarity < threshold (topic change)
            # - OR adding next sentence exceeds target_tokens
            segments: List[List[str]] = []
            current_segment: List[str] = [sentences[0]]
            current_tokens = approximate_tokens_from_words(sentences[0])

            for i in range(len(similarities)):
                next_sentence = sentences[i + 1]
                next_tokens = approximate_tokens_from_words(next_sentence)
                sim = similarities[i]

                # Check boundary condition
                is_topic_change = sim < threshold
                exceeds_size = (current_tokens + next_tokens) > target_tokens

                if (is_topic_change or exceeds_size) and current_segment:
                    segments.append(current_segment)
                    current_segment = [next_sentence]
                    current_tokens = next_tokens
                else:
                    current_segment.append(next_sentence)
                    current_tokens += next_tokens

            if current_segment:
                segments.append(current_segment)

            # Apply overlap across segments
            # If target_overlap > 0, carry over trailing sentences from prior segment
            overlap_sentences_count = 1 if target_overlap > 0 else 0

            final_page_chunks: List[str] = []
            for seg_idx, segment in enumerate(segments):
                if seg_idx > 0 and overlap_sentences_count > 0:
                    prior_segment = segments[seg_idx - 1]
                    overlap_part = prior_segment[-overlap_sentences_count:]
                    # Avoid duplicate prepending if sentence is already in segment
                    combined = [s for s in overlap_part if s not in segment] + segment
                    final_page_chunks.append(" ".join(combined))
                else:
                    final_page_chunks.append(" ".join(segment))

            # Emit Chunk objects
            for chunk_text in final_page_chunks:
                cleaned = chunk_text.strip()
                if not cleaned:
                    continue
                token_count = approximate_tokens_from_words(cleaned)
                meta = ChunkMetadata(
                    documentId=document_id,
                    documentName=document_name,
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=global_chunk_idx,
                    chunkingMethod="semantic",
                    pageNumber=page.page_number,
                    tokenCountApprox=token_count,
                    characterCount=len(cleaned),
                )
                chunks.append(Chunk(content=cleaned, metadata=meta))
                global_chunk_idx += 1

        return chunks

    # -------------------------------------------------------------------------
    # Unified Chunking Interface
    # -------------------------------------------------------------------------
    def chunk_document(
        self,
        document: Union[str, ExtractedDocument, List[ExtractedPage]],
        method: ChunkingMethodType = "recursive",
        document_id: str = "doc_default",
        document_name: str = "document",
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
        **kwargs,
    ) -> List[Chunk]:
        clean_method = method.lower().strip() if isinstance(method, str) else ""

        if clean_method == "recursive":
            return self.recursive_chunking(
                document=document,
                document_id=document_id,
                document_name=document_name,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
                **kwargs,
            )
        elif clean_method == "fixed":
            return self.fixed_chunking(
                document=document,
                document_id=document_id,
                document_name=document_name,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
            )
        elif clean_method == "semantic":
            return self.semantic_chunking(
                document=document,
                document_id=document_id,
                document_name=document_name,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
                **kwargs,
            )
        else:
            raise ValueError(
                f"Unknown chunking method '{method}'. Supported methods are 'fixed', 'recursive', 'semantic'."
            )
