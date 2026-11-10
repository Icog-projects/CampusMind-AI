"""
CampusMind AI - RAG Orchestration Service
Orchestrates the complete Retrieval-Augmented Generation pipeline:
1. Question normalization and deterministic cache key check via RedisCacheService.
2. Immediate short-circuit return on cache hit (skips embedding, retrieval, and LLM).
3. On cache miss:
   - Computes query embedding via EmbeddingService.
   - Executes hybrid retrieval (BM25 + Qdrant Cosine) via HybridRetrievalService.
   - Generates cited, grounded answer via GenerationService.
4. Caches only successful, sufficiently grounded answers into Redis.
5. Handles document knowledge-base invalidation cleanly.
"""

import logging
from typing import Optional, Sequence

from app.schemas.chunk import GroundedAnswer, ScoredChunk
from app.services.cache_service import RedisCacheService, DEFAULT_ACCESS_SCOPE
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retrieval import HybridRetrievalService
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)


class RAGService:
    """
    End-to-end RAG orchestrator integrating Cache, Embedding, Hybrid Retrieval, and Generation.
    """

    def __init__(
        self,
        cache_service: Optional[RedisCacheService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        hybrid_retrieval_service: Optional[HybridRetrievalService] = None,
        generation_service: Optional[GenerationService] = None,
    ):
        """
        Initializes the RAGService with required dependencies.

        Args:
            cache_service: RedisCacheService instance.
            embedding_service: EmbeddingService instance.
            hybrid_retrieval_service: HybridRetrievalService instance.
            generation_service: GenerationService instance.
        """
        self.cache_service = cache_service or RedisCacheService()
        self.embedding_service = embedding_service
        self.hybrid_retrieval_service = hybrid_retrieval_service
        self.generation_service = generation_service or GenerationService()

    def query(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        filter_document_id: Optional[str] = None,
        top_k: int = 5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> GroundedAnswer:
        """
        Processes a user query end-to-end with cache-aside lookup.

        Args:
            question: User question string.
            scope: Access scope / permission tier (default: 'public').
            filter_document_id: Optional documentId filter.
            top_k: Number of chunks to fuse in hybrid retrieval.
            temperature: LLM generation temperature.
            max_tokens: LLM generation token limit.

        Returns:
            GroundedAnswer containing the answer text, citations, and metadata.
        """
        if not isinstance(question, str):
            raise TypeError(f"question must be a string, got {type(question)}")

        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty.")

        # Step 1: Check Redis cache before running embedding, retrieval, or LLM
        cached_answer = None
        try:
            cached_answer = self.cache_service.get_answer(
                question=cleaned_question,
                scope=scope,
            )
        except Exception as e:
            logger.warning("Cache lookup error, falling back to RAG pipeline: %s", e)

        if cached_answer is not None:
            logger.info("Serving answer from cache for query: '%s' (scope: %s)", cleaned_question, scope)
            return cached_answer

        # Step 2: Cache miss - generate query embedding if embedding service available
        query_vector = None
        if self.embedding_service is not None:
            try:
                query_vector = self.embedding_service.embed_query(cleaned_question)
            except Exception as e:
                logger.warning("Query embedding generation failed: %s", e)

        # Step 3: Hybrid Retrieval (BM25 + Qdrant Vector)
        retrieved_chunks: Sequence[ScoredChunk] = []
        if self.hybrid_retrieval_service is not None:
            try:
                retrieved_chunks = self.hybrid_retrieval_service.search(
                    query=cleaned_question,
                    query_vector=query_vector,
                    top_k=top_k,
                    filter_document_id=filter_document_id,
                )
            except Exception as e:
                logger.warning("Hybrid retrieval failed: %s", e)
                retrieved_chunks = []

        # Step 4: Grounded Generation with citation mapping
        answer = self.generation_service.generate_answer(
            question=cleaned_question,
            retrieved_chunks=retrieved_chunks,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Step 5: Cache only successful grounded answers with sufficient context
        if answer.has_sufficient_context and answer.sources:
            try:
                self.cache_service.set_answer(
                    question=cleaned_question,
                    answer=answer,
                    scope=scope,
                )
            except Exception as e:
                logger.warning("Failed to store answer in cache: %s", e)

        return answer

    def invalidate_knowledge_base(self, new_version: str):
        """
        Invalidates cached answers when documents in the knowledge base change
        by rotating the active knowledge-base version.
        """
        self.cache_service.update_kb_version(new_version)
