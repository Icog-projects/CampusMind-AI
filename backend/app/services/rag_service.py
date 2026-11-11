"""CampusMind AI - RAG Orchestration Service.

Coordinates cache lookup, semantic caching, query embedding, hybrid retrieval, reranking, and grounded generation.

Responsibilities:
Class RAGService:
1. RAGService.__init__(): Initializes the orchestrator with cache, semantic cache, embedding, retrieval, reranking, and generation services.
2. RAGService.query(): Executes the complete cache-aside RAG pipeline for a user question.
3. RAGService.invalidate_knowledge_base(): Rotates knowledge-base version to invalidate cached answers.
"""

import logging
from typing import Optional, Sequence

from app.schemas.chunk import GroundedAnswer, ScoredChunk
from app.services.cache_service import RedisCacheService, DEFAULT_ACCESS_SCOPE, generate_cache_key
from app.services.semantic_cache_service import SemanticCacheService
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retrieval import HybridRetrievalService
from app.services.reranking_service import RerankingService
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)


# End-to-end RAG orchestrator integrating Cache, Semantic Cache, Embedding, Hybrid Retrieval, Reranking, and Generation.
class RAGService:

    # Initializes the RAGService with required dependencies.
    def __init__(
        self,
        cache_service: Optional[RedisCacheService] = None,
        semantic_cache_service: Optional[SemanticCacheService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        hybrid_retrieval_service: Optional[HybridRetrievalService] = None,
        reranking_service: Optional[RerankingService] = None,
        generation_service: Optional[GenerationService] = None,
    ):
        self.cache_service = cache_service or RedisCacheService()
        self.semantic_cache_service = semantic_cache_service
        self.embedding_service = embedding_service
        self.hybrid_retrieval_service = hybrid_retrieval_service
        self.reranking_service = reranking_service
        self.generation_service = generation_service or GenerationService()

    # Processes a user query end-to-end with cache-aside lookup and hybrid retrieval.
    def query(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        filter_document_id: Optional[str] = None,
        top_k: int = 5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> GroundedAnswer:
        if not isinstance(question, str):
            raise TypeError(f"question must be a string, got {type(question)}")

        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty.")

        # Step 1: Check exact Redis cache before running embedding, retrieval, or LLM
        cached_answer = None
        try:
            cached_answer = self.cache_service.get_answer(
                question=cleaned_question,
                scope=scope,
            )
        except Exception as e:
            logger.warning("Exact cache lookup error, falling back to pipeline: %s", e)

        if cached_answer is not None:
            logger.info("Serving answer from exact cache for query: '%s' (scope: %s)", cleaned_question, scope)
            return cached_answer

        # Step 2: Exact cache miss - generate query embedding (reused for semantic cache and vector retrieval)
        query_vector = None
        if self.embedding_service is not None:
            try:
                query_vector = self.embedding_service.embed_query(cleaned_question)
            except Exception as e:
                logger.warning("Query embedding generation failed: %s", e)

        # Step 3: Check semantic cache if query embedding and semantic cache service are available
        if self.semantic_cache_service is not None and query_vector is not None:
            try:
                kb_ver = getattr(self.cache_service, "kb_version", "v1")
                semantic_hit = self.semantic_cache_service.search_similar(
                    query_vector=query_vector,
                    scope=scope,
                    kb_version=kb_ver,
                )
                if semantic_hit and semantic_hit.get("cache_key"):
                    stored_key = semantic_hit["cache_key"]
                    semantic_answer = self.cache_service.get_answer_by_key(stored_key)
                    if semantic_answer is not None:
                        logger.info(
                            "Serving answer from semantic cache (score=%.4f, key=%s) for query: '%s'",
                            semantic_hit.get("score", 0.0),
                            stored_key,
                            cleaned_question,
                        )
                        return semantic_answer
                    else:
                        logger.info("Semantic match found (%s), but Redis entry expired or missing.", stored_key)
            except Exception as e:
                logger.warning("Semantic cache lookup error, continuing with RAG pipeline: %s", e)

        # Step 4: Hybrid Retrieval (BM25 + Qdrant Vector) - reuses query_vector
        retrieved_chunks: Sequence[ScoredChunk] = []
        if self.hybrid_retrieval_service is not None:
            try:
                # If reranking service is configured, retrieve a broader pool (up to 20 or top_k * 2)
                candidate_k = max(top_k * 2, 10) if self.reranking_service is not None else top_k
                retrieved_chunks = self.hybrid_retrieval_service.search(
                    query=cleaned_question,
                    query_vector=query_vector,
                    top_k=candidate_k,
                    filter_document_id=filter_document_id,
                )
            except Exception as e:
                logger.warning("Hybrid retrieval failed: %s", e)
                retrieved_chunks = []

        # Step 5: Reranking with CrossEncoder (runs only on cache misses)
        if self.reranking_service is not None and retrieved_chunks:
            try:
                retrieved_chunks = self.reranking_service.rerank(
                    query=cleaned_question,
                    candidates=retrieved_chunks,
                    top_k=top_k,
                )
            except Exception as e:
                logger.warning("Reranking failed, using original retrieval order: %s", e)
                retrieved_chunks = retrieved_chunks[:top_k]
        else:
            retrieved_chunks = retrieved_chunks[:top_k]

        # Step 6: Grounded Generation with citation mapping
        answer = self.generation_service.generate_answer(
            question=cleaned_question,
            retrieved_chunks=retrieved_chunks,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Step 7: Cache grounded answers with sufficient context in Redis AND semantic cache
        if answer.has_sufficient_context and answer.sources:
            try:
                self.cache_service.set_answer(
                    question=cleaned_question,
                    answer=answer,
                    scope=scope,
                )
                # Store in semantic cache collection
                if self.semantic_cache_service is not None and query_vector is not None:
                    kb_ver = getattr(self.cache_service, "kb_version", "v1")
                    cache_key = generate_cache_key(
                        question=cleaned_question,
                        kb_version=kb_ver,
                        scope=scope,
                        namespace=self.cache_service.namespace,
                    )
                    self.semantic_cache_service.store(
                        question=cleaned_question,
                        query_vector=query_vector,
                        cache_key=cache_key,
                        scope=scope,
                        kb_version=kb_ver,
                    )
            except Exception as e:
                logger.warning("Failed to store answer in cache: %s", e)

        return answer

    # Rotates active knowledge-base version to invalidate cached answers.
    def invalidate_knowledge_base(self, new_version: str):
        self.cache_service.update_kb_version(new_version)
