"""
Tests for Semantic Caching Service in CampusMind AI.

Verifies:
1. Exact cache hit returns answer immediately without calling semantic cache or embedding.
2. Semantic cache hit for differently worded but equivalent questions returns the cached answer.
3. Semantic cache miss for unrelated questions continues to RAG pipeline.
4. Similarity below threshold does not produce a semantic cache hit.
5. Expired or missing Redis entry with existing Qdrant point gracefully misses and falls back to RAG pipeline.
6. Different access scopes do not share cached answers.
7. Different knowledge-base versions do not share cached answers.
8. Query embedding generated during semantic cache check is reused for vector retrieval.
9. Grounded answers with sufficient context are saved to both Redis and semantic cache.
10. Insufficient context answers are not cached into semantic cache.
"""

import pytest
from unittest.mock import MagicMock

from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk, GroundedAnswer, SourceCitation
from app.services.cache_service import RedisCacheService, generate_cache_key
from app.services.semantic_cache_service import SemanticCacheService, DEFAULT_SEMANTIC_CACHE_COLLECTION
from app.services.rag_service import RAGService


def make_test_scored_chunk() -> ScoredChunk:
    chunk = Chunk(
        content="Campus library is open from 8:00 AM to 10:00 PM on weekdays.",
        metadata=ChunkMetadata(
            documentId="doc-library",
            documentName="LibraryHours.pdf",
            chunkId="chk-lib-01",
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=1,
            characterCount=60,
        ),
    )
    return ScoredChunk(chunk=chunk, score=0.95, retrieval_method="hybrid")


def make_test_grounded_answer(has_context: bool = True) -> GroundedAnswer:
    sources = []
    if has_context:
        sources = [
            SourceCitation(
                citation_index=1,
                document_id="doc-library",
                document_name="LibraryHours.pdf",
                page_number=1,
                chunk_id="chk-lib-01",
                chunk_index=0,
                content_snippet="Campus library is open from 8:00 AM to 10:00 PM on weekdays.",
            )
        ]
    return GroundedAnswer(
        answer="The campus library is open from 8:00 AM to 10:00 PM on weekdays [1]." if has_context else "No information available.",
        sources=sources,
        has_sufficient_context=has_context,
        model_name="openai/gpt-oss-120b",
    )


# 1. Exact cache hit bypasses semantic cache and downstream pipeline
def test_exact_cache_hit_bypasses_semantic_cache():
    mock_cache = MagicMock(spec=RedisCacheService)
    cached_ans = make_test_grounded_answer(has_context=True)
    mock_cache.get_answer.return_value = cached_ans

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_embedding = MagicMock()
    mock_retrieval = MagicMock()
    mock_generation = MagicMock()

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="What are library hours?")

    assert result == cached_ans
    assert mock_cache.get_answer.called
    assert not mock_semantic.search_similar.called
    assert not mock_embedding.embed_query.called
    assert not mock_retrieval.search.called
    assert not mock_generation.generate_answer.called


# 2. Semantic cache hit for differently worded question
def test_semantic_cache_hit_returns_cached_answer():
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None  # Exact cache miss
    cached_ans = make_test_grounded_answer(has_context=True)

    # Stored key in Redis
    test_key = "campusmind:answer:v1:public:abc123hash"
    mock_cache.get_answer_by_key.side_effect = lambda k: cached_ans if k == test_key else None
    mock_cache.kb_version = "v1"

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_semantic.search_similar.return_value = {
        "cache_key": test_key,
        "question": "What time does the library open and close?",
        "score": 0.94,
        "scope": "public",
        "kb_version": "v1",
    }

    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 384

    mock_retrieval = MagicMock()
    mock_generation = MagicMock()

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    # Ask differently worded query
    result = rag.query(question="When is the library open?")

    assert result == cached_ans
    assert mock_cache.get_answer.called
    assert mock_embedding.embed_query.called
    assert mock_semantic.search_similar.called
    assert mock_cache.get_answer_by_key.called
    # Downstream generation must NOT be called on semantic hit
    assert not mock_retrieval.search.called
    assert not mock_generation.generate_answer.called


# 3. Semantic cache miss for unrelated questions continues to RAG pipeline
def test_semantic_cache_miss_continues_to_pipeline():
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None
    mock_cache.kb_version = "v1"
    mock_cache.namespace = "campusmind:answer"

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_semantic.search_similar.return_value = None  # No similar match

    mock_embedding = MagicMock()
    q_vec = [0.2] * 384
    mock_embedding.embed_query.return_value = q_vec

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = [make_test_scored_chunk()]

    mock_generation = MagicMock()
    new_ans = make_test_grounded_answer(has_context=True)
    mock_generation.generate_answer.return_value = new_ans

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="How do I register for courses?")

    assert result == new_ans
    assert mock_retrieval.search.called
    assert mock_generation.generate_answer.called
    # Must save into both Redis cache and semantic cache
    assert mock_cache.set_answer.called
    assert mock_semantic.store.called


# 4. Expired or missing Redis entry with Qdrant match falls back to RAG pipeline
def test_semantic_hit_with_expired_redis_entry_falls_back():
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None
    mock_cache.get_answer_by_key.return_value = None  # Expired in Redis!
    mock_cache.kb_version = "v1"
    mock_cache.namespace = "campusmind:answer"

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_semantic.search_similar.return_value = {
        "cache_key": "campusmind:answer:v1:public:expiredkey",
        "question": "What are library hours?",
        "score": 0.96,
        "scope": "public",
        "kb_version": "v1",
    }

    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 384

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = [make_test_scored_chunk()]

    mock_generation = MagicMock()
    fresh_ans = make_test_grounded_answer(has_context=True)
    mock_generation.generate_answer.return_value = fresh_ans

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="Library opening time?")

    assert result == fresh_ans
    assert mock_cache.get_answer_by_key.called
    # RAG pipeline executed because Redis entry had expired
    assert mock_retrieval.search.called
    assert mock_generation.generate_answer.called


# 5. Access scopes isolation: public vs staff
def test_semantic_cache_respects_access_scope():
    from qdrant_client import QdrantClient

    client = QdrantClient(":memory:")
    sem_service = SemanticCacheService(qdrant_client=client, similarity_threshold=0.85)

    q_vec = [0.05] * 384
    # Store under staff scope
    sem_service.store(
        question="Staff salary scale",
        query_vector=q_vec,
        cache_key="campusmind:answer:v1:all:staffkey123",
        scope="all",
        kb_version="v1",
    )

    # Search under public scope
    hit_public = sem_service.search_similar(
        query_vector=q_vec,
        scope="public",
        kb_version="v1",
    )
    assert hit_public is None, "Public scope must NOT match staff/all scope entry"

    # Search under staff scope
    hit_staff = sem_service.search_similar(
        query_vector=q_vec,
        scope="all",
        kb_version="v1",
    )
    assert hit_staff is not None
    assert hit_staff["cache_key"] == "campusmind:answer:v1:all:staffkey123"


# 6. Knowledge-base version isolation: v1 vs v2
def test_semantic_cache_respects_kb_version():
    from qdrant_client import QdrantClient

    client = QdrantClient(":memory:")
    sem_service = SemanticCacheService(qdrant_client=client, similarity_threshold=0.85)

    q_vec = [0.08] * 384
    sem_service.store(
        question="Graduation requirements",
        query_vector=q_vec,
        cache_key="campusmind:answer:v1:public:gradkey1",
        scope="public",
        kb_version="v1",
    )

    # Search with v2
    hit_v2 = sem_service.search_similar(
        query_vector=q_vec,
        scope="public",
        kb_version="v2",
    )
    assert hit_v2 is None, "New KB version must NOT match old KB version cached query"

    # Search with v1
    hit_v1 = sem_service.search_similar(
        query_vector=q_vec,
        scope="public",
        kb_version="v1",
    )
    assert hit_v1 is not None
    assert hit_v1["cache_key"] == "campusmind:answer:v1:public:gradkey1"


# 7. Similarity threshold test: below threshold rejects match
def test_semantic_cache_threshold_filtering():
    from qdrant_client import QdrantClient

    client = QdrantClient(":memory:")
    # Set threshold high: 0.95
    sem_service = SemanticCacheService(qdrant_client=client, similarity_threshold=0.95)

    vec1 = [0.1] * 384
    sem_service.store(
        question="What is the tuition fee?",
        query_vector=vec1,
        cache_key="campusmind:answer:v1:public:tuition123",
        scope="public",
        kb_version="v1",
    )

    # Create a vector that is somewhat similar but below 0.95 cosine
    vec_diff = [0.1] * 192 + [-0.1] * 192

    hit = sem_service.search_similar(
        query_vector=vec_diff,
        scope="public",
        kb_version="v1",
    )
    assert hit is None


# 8. Query vector reuse between semantic cache check and vector retrieval
def test_query_vector_reused_in_vector_search():
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None
    mock_cache.kb_version = "v1"
    mock_cache.namespace = "campusmind:answer"

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_semantic.search_similar.return_value = None

    mock_embedding = MagicMock()
    fixed_vector = [0.33] * 384
    mock_embedding.embed_query.return_value = fixed_vector

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = [make_test_scored_chunk()]

    mock_generation = MagicMock()
    mock_generation.generate_answer.return_value = make_test_grounded_answer(has_context=True)

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    rag.query(question="Tell me about parking permits")

    # embed_query must be called exactly ONCE
    assert mock_embedding.embed_query.call_count == 1
    # semantic cache searched with fixed_vector
    mock_semantic.search_similar.assert_called_once_with(
        query_vector=fixed_vector,
        scope="public",
        kb_version="v1",
    )
    # hybrid retrieval search called with identical query_vector
    _, kwargs = mock_retrieval.search.call_args
    assert kwargs.get("query_vector") == fixed_vector


# 9. Insufficient context answer is NOT saved in semantic cache
def test_insufficient_context_not_saved_in_semantic_cache():
    mock_cache = MagicMock(spec=RedisCacheService)
    mock_cache.get_answer.return_value = None

    mock_semantic = MagicMock(spec=SemanticCacheService)
    mock_semantic.search_similar.return_value = None

    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 384

    mock_retrieval = MagicMock()
    mock_retrieval.search.return_value = []

    mock_generation = MagicMock()
    # Insufficient context answer
    ungrounded_ans = make_test_grounded_answer(has_context=False)
    mock_generation.generate_answer.return_value = ungrounded_ans

    rag = RAGService(
        cache_service=mock_cache,
        semantic_cache_service=mock_semantic,
        embedding_service=mock_embedding,
        hybrid_retrieval_service=mock_retrieval,
        generation_service=mock_generation,
    )

    result = rag.query(question="What is the secret passkey?")

    assert result == ungrounded_ans
    assert not mock_cache.set_answer.called
    assert not mock_semantic.store.called

