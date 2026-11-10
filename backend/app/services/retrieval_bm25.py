"""CampusMind AI - BM25 Retrieval Service.

Provides Okapi BM25 keyword search and indexing over document chunks.

Responsibilities:
1. default_tokenizer(): Tokenizes text into lowercase alphanumeric words.
Class BM25RetrievalService:
2. BM25RetrievalService.__init__(): Initializes the BM25 index structures and tokenizer.
3. BM25RetrievalService.is_indexed(): Reports whether the BM25 index currently contains searchable chunks.
4. BM25RetrievalService.total_chunks(): Returns the count of indexed chunks.
5. BM25RetrievalService.build_index(): Builds or rebuilds the BM25 inverted index from a sequence of chunks.
6. BM25RetrievalService.clear_index(): Clears all indexed chunks and resets the search state.
7. BM25RetrievalService.search(): Performs BM25 keyword scoring over indexed chunks with optional document filtering.
8. BM25RetrievalService.add_chunks(): Appends new chunks to the corpus and updates the index.
9. BM25RetrievalService.remove_document(): Deletes all chunks associated with a document ID from the index.
"""

import re
import logging
from typing import List, Optional, Sequence, Set
from rank_bm25 import BM25Okapi

from app.schemas.chunk import Chunk, ScoredChunk

logger = logging.getLogger(__name__)


# Standard lowercased alphanumeric tokenizer.
def default_tokenizer(text: str) -> List[str]:
    if not text:
        return []
    # Match alphanumeric words of length >= 1
    return [token.lower() for token in re.findall(r"\w+", text)]


# Provides Okapi BM25 keyword search and indexing over document chunks.
class BM25RetrievalService:

    # Initializes the BM25 retrieval service and internal corpus storage.
    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer or default_tokenizer
        self._chunks: List[Chunk] = []
        self._tokenized_corpus: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

    # Indicates whether the BM25 index is built and ready for search.
    @property
    def is_indexed(self) -> bool:
        return self._bm25 is not None and len(self._chunks) > 0

    # Returns the total number of indexed chunks.
    @property
    def total_chunks(self) -> int:
        return len(self._chunks)

    # Builds or rebuilds the BM25 index from the given chunks.
    def build_index(self, chunks: Sequence[Chunk], deduplicate: bool = True) -> int:
        if not chunks:
            self.clear_index()
            return 0

        unique_chunks: List[Chunk] = []
        seen_ids: Set[str] = set()

        for chunk in chunks:
            if not isinstance(chunk, Chunk):
                raise TypeError(f"Expected Chunk instance, got {type(chunk)}")
            
            # Deduplicate by unique chunk_id if present
            chunk_id = chunk.metadata.chunk_id
            if deduplicate and chunk_id in seen_ids:
                continue

            seen_ids.add(chunk_id)
            unique_chunks.append(chunk)

        tokenized_corpus = []
        valid_chunks = []

        for chunk in unique_chunks:
            tokens = self.tokenizer(chunk.content)
            # Retain even if tokens is empty to preserve chunk alignment, but give empty token list
            tokenized_corpus.append(tokens)
            valid_chunks.append(chunk)

        if not valid_chunks:
            self.clear_index()
            return 0

        self._chunks = valid_chunks
        self._tokenized_corpus = tokenized_corpus
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info("Successfully built BM25 index with %d chunks.", len(self._chunks))
        return len(self._chunks)

    # Clears the existing index and all associated chunks.
    def clear_index(self):
        self._chunks = []
        self._tokenized_corpus = []
        self._bm25 = None

    # Performs BM25 keyword search against the indexed chunks.
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        filter_document_id: Optional[str] = None,
    ) -> List[ScoredChunk]:
        if top_k <= 0:
            raise ValueError(f"top_k must be a positive integer, got {top_k}")

        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query)}")

        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        if not self.is_indexed:
            logger.warning("BM25 search called on an empty or uninitialized index.")
            return []

        query_tokens = self.tokenizer(cleaned_query)
        if not query_tokens:
            return []

        # Compute Okapi BM25 scores across all indexed chunks
        scores = self._bm25.get_scores(query_tokens)

        # Pair scores with their original Chunk objects
        results: List[ScoredChunk] = []
        for chunk, score in zip(self._chunks, scores):
            if filter_document_id and chunk.metadata.document_id != filter_document_id:
                continue

            float_score = float(score)
            if float_score > min_score:
                results.append(
                    ScoredChunk(
                        chunk=chunk,
                        score=float_score,
                        retrieval_method="bm25",
                    )
                )

        # Sort descending by score
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    # Adds new chunks to existing collection and rebuilds index.
    def add_chunks(self, new_chunks: Sequence[Chunk], deduplicate: bool = True) -> int:
        combined = list(self._chunks) + list(new_chunks)
        return self.build_index(combined, deduplicate=deduplicate)

    # Removes all chunks associated with a specific documentId and rebuilds the index.
    def remove_document(self, document_id: str) -> int:
        if not self.is_indexed:
            return 0

        remaining = [c for c in self._chunks if c.metadata.document_id != document_id]
        return self.build_index(remaining, deduplicate=False)

