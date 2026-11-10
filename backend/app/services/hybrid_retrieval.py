"""CampusMind AI - Hybrid Retrieval Service.

Fuses lexical BM25 and dense vector search results using Reciprocal Rank Fusion (RRF).

Responsibilities:
1. compute_rrf(): Combines ranked candidate chunk lists using the Reciprocal Rank Fusion formula.
Class HybridRetrievalService:
2. HybridRetrievalService.__init__(): Initializes BM25, vector store, and fusion configuration parameters.
3. HybridRetrievalService.search(): Executes parallel lexical and semantic searches and returns fused results.
"""

import logging
from typing import List, Optional, Dict, Sequence, Any, Union

from app.schemas.chunk import Chunk, ScoredChunk
from app.services.retrieval_bm25 import BM25RetrievalService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_LIMIT = 20
DEFAULT_TOP_K = 5


def compute_rrf(
    ranked_lists: Sequence[Sequence[ScoredChunk]],
    k: int = DEFAULT_RRF_K,
    top_k: int = DEFAULT_TOP_K,
) -> List[ScoredChunk]:
    """
    Computes Reciprocal Rank Fusion over multiple ranked lists of ScoredChunks.

    Args:
        ranked_lists: A sequence of ranked lists (e.g. [bm25_results, vector_results]).
        k: Smoothing constant for RRF (must be >= 1, standard default is 60).
        top_k: Maximum number of fused items to return (must be >= 1).

    Returns:
        List[ScoredChunk] ordered by descending RRF score, with retrieval_method="hybrid".
    """
    if k <= 0:
        raise ValueError(f"RRF constant k must be positive, got {k}")
    if top_k <= 0:
        raise ValueError(f"top_k must be positive, got {top_k}")

    # Map chunk_id -> (cumulative_rrf_score, Chunk)
    fused_scores: Dict[str, float] = {}
    chunk_store: Dict[str, Chunk] = {}

    for result_list in ranked_lists:
        if not result_list:
            continue

        # Each result_list is ranked from 1 to N
        for rank_idx, scored_chunk in enumerate(result_list, start=1):
            if not isinstance(scored_chunk, ScoredChunk):
                continue

            chunk = scored_chunk.chunk
            chunk_id = chunk.metadata.chunk_id

            score_contribution = 1.0 / (k + rank_idx)
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + score_contribution

            # Store or preserve chunk object
            if chunk_id not in chunk_store:
                chunk_store[chunk_id] = chunk

    if not fused_scores:
        return []

    # Sort chunks by descending RRF score
    sorted_items = sorted(
        fused_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    fused_results: List[ScoredChunk] = []
    for chunk_id, rrf_score in sorted_items[:top_k]:
        fused_results.append(
            ScoredChunk(
                chunk=chunk_store[chunk_id],
                score=rrf_score,
                retrieval_method="hybrid",
            )
        )

    return fused_results


class HybridRetrievalService:
    """
    Orchestrates hybrid retrieval by querying BM25 and Qdrant VectorStore
    and merging candidates with Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        bm25_service: Optional[BM25RetrievalService] = None,
        vector_store: Optional[VectorStoreService] = None,
        default_k: int = DEFAULT_RRF_K,
        default_candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ):
        """
        Initializes the HybridRetrievalService.

        Args:
            bm25_service: Instance of BM25RetrievalService (optional).
            vector_store: Instance of VectorStoreService (optional).
            default_k: Default RRF smoothing factor (default: 60).
            default_candidate_limit: Default number of candidates to pull from each sub-service.
        """
        self.bm25_service = bm25_service
        self.vector_store = vector_store
        self.default_k = default_k
        self.default_candidate_limit = default_candidate_limit

    def search(
        self,
        query: str,
        query_vector: Optional[Sequence[float]] = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_limit: Optional[int] = None,
        k: Optional[int] = None,
        filter_document_id: Optional[str] = None,
    ) -> List[ScoredChunk]:
        """
        Performs hybrid retrieval combining BM25 keyword search and dense vector search.

        Args:
            query: Keyword query string for BM25.
            query_vector: Dense embedding vector for Qdrant vector search.
            top_k: Number of final fused results to return.
            candidate_limit: Number of candidates to retrieve from each individual searcher.
            k: RRF smoothing constant (default: 60).
            filter_document_id: Optional documentId filter to narrow results.

        Returns:
            List[ScoredChunk] with retrieval_method="hybrid".
        """
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")

        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query)}")

        cleaned_query = query.strip()
        candidates_k = candidate_limit or self.default_candidate_limit
        if candidates_k <= 0:
            raise ValueError(f"candidate_limit must be positive, got {candidates_k}")

        rrf_k = k or self.default_k
        if rrf_k <= 0:
            raise ValueError(f"k must be positive, got {rrf_k}")

        ranked_lists: List[List[ScoredChunk]] = []

        # 1. Execute BM25 search if available and query is non-empty
        if self.bm25_service is not None and cleaned_query:
            try:
                bm25_candidates = self.bm25_service.search(
                    query=cleaned_query,
                    top_k=candidates_k,
                    filter_document_id=filter_document_id,
                )
                ranked_lists.append(bm25_candidates)
            except Exception as e:
                logger.warning("BM25 retrieval failed or was unavailable: %s", e)

        # 2. Execute Qdrant vector search if available and query_vector is provided
        if self.vector_store is not None and query_vector:
            try:
                vector_candidates = self.vector_store.search(
                    query_vector=query_vector,
                    top_k=candidates_k,
                    filter_document_id=filter_document_id,
                )
                ranked_lists.append(vector_candidates)
            except Exception as e:
                logger.warning("Vector store retrieval failed or was unavailable: %s", e)

        # 3. If neither or only one returned, compute_rrf handles empty/single lists gracefully
        return compute_rrf(ranked_lists=ranked_lists, k=rrf_k, top_k=top_k)

