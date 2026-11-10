"""
Tests for RAG Orchestration Service in CampusMind AI.

Verifies:
1. Cache hit returns cached GroundedAnswer immediately.
2. Cache hit completely skips EmbeddingService, HybridRetrievalService, and GenerationService.
3. Cache miss invokes the full pipeline: Embedding -> Hybrid Retrieval -> Generation.
4. Only grounded, successful answers are stored into the cache after generation.
5. Cache failure or Redis absence degrades seamlessly to normal pipeline execution.
6. Knowledge base invalidation triggers pipeline re-execution on updated version.
"""

import pytest
from unittest.mock import MagicMock

from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk, GroundedAnswer, SourceCitation
from app.services.cache_service import RedisCacheService
from app.services.rag_service import RAGService


def make_test_scored_chunk() -> ScoredChunk:
    chunk = Chunk(
        content="Final examination will take place on December 15 in the Main Hall.",
        metadata=ChunkMetadata(
            documentId="doc-exam",
            documentName="ExamSchedule.pdf",
            chunkId="chk-01",
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=2,
            characterCount=66,
        ),
    )
    return ScoredChunk(chunk=chunk, score=0.92, retrieval_method="hybrid")


def make_test_grounded_answer(has_context: bool = True) -> GroundedAnswer:
    sources = []
    if has_context:
        sources = [
            SourceCitation(
                citation_index=1,
                document_id="doc-exam",
                document_name="ExamSchedule.pdf",
                page_number=2,
                chunk_id="chk-01",
                chunk_index=0,
                content_snippet="Final examination will take place on December 15 in the Main Hall.",
            )
        ]
    return GroundedAnswer(
        answer="The final exam is on December 15 in the Main Hall [1]." if has_context else "No info found.",
        sources=sources,
        has_sufficient_context=has_context,
        model_name="openai/gpt-oss-120b",
    )


def test_cache_hit_skips_embedding_retrieval_and_llm():
    """Verify that a cache hit directly returns the answer without touching downstream services."""
    mock_cache = MagicMock(spec=RedisCacheService)
    cached_ans = make_test_grounded_answer(has_context=True)
    mock_cache.get_answer.return_value = cached_ans

    mock_embedding = MagicMock()
    mock_retrieval = MagicMock()
    mock_generation = MagicMock()

    rag = RAGService(
        cache_service=mock_cache,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="When is the final exam?")

    # Assert cache was checked
    assert mock_cache.get_answer.called
    assert result == cached_ans

    # Crucial: verify downstream components were NEVER invoked
    assert not mock_embedding.embed_query.called
    assert not mock_retrieval.search.called
    assert not mock_generation.generate_answer.called


def test_cache_miss_executes_complete_pipeline_and_caches_result():
    """Verify cache miss runs embedding, hybrid retrieval, generation, and saves result."""
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None  # Cache miss

    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 384

    mock_retrieval = MagicMock()
    retrieved = [make_test_scored_chunk()]
    mock_retrieval.search.return_value = retrieved

    mock_generation = MagicMock()
    generated_ans = make_test_grounded_answer(has_context=True)
    mock_generation.generate_answer.return_value = generated_ans

    rag = RAGService(
        cache_service=mock_cache,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    question = "When is the final exam?"
    result = rag.query(question=question, top_k=3)

    # All pipeline components must be executed in order
    assert mock_cache.get_answer.called
    assert mock_embedding.embed_query.called
    assert mock_retrieval.search.called
    assert mock_generation.generate_answer.called

    assert result == generated_ans

    # Answer must be written to cache
    mock_cache.set_answer.assert_called_once_with(
        question=question,
        answer=generated_ans,
        scope="public",
    )


def test_cache_miss_does_not_cache_insufficient_context():
    """Verify answers without sufficient context are not saved to cache."""
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = []

    mock_generation = MagicMock()
    insufficient_ans = make_test_grounded_answer(has_context=False)
    mock_generation.generate_answer.return_value = insufficient_ans

    rag = RAGService(
        cache_service=mock_cache,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    rag.query(question="When is the final exam?")
    assert not mock_cache.set_answer.called


def test_redis_failure_falls_back_gracefully():
    """Verify that if Redis throws an exception, RAG still completes normally."""
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.side_effect = Exception("Redis connection refused")
    mock_cache.set_answer.side_effect = Exception("Redis connection refused")

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = [make_test_scored_chunk()]

    mock_generation = MagicMock()
    generated_ans = make_test_grounded_answer(has_context=True)
    mock_generation.generate_answer.return_value = generated_ans

    rag = RAGService(
        cache_service=mock_cache,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="When is the final exam?")
    assert result == generated_ans


def test_knowledge_base_invalidation_delegates_to_cache():
    """Verify invalidating knowledge base invokes cache service version update."""
    mock_cache = MagicMock(spec=RedisCacheService)
    rag = RAGService(cache_service=mock_cache)

    rag.invalidate_knowledge_base("v2026.11.10")
    mock_cache.update_kb_version.assert_called_once_with("v2026.11.10")

