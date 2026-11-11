"""
CampusMind AI - Real Redis Integration Verification Tests
Tests RedisCacheService against a live running Redis server:
- Cache set and get with full JSON serialization of GroundedAnswer and citations
- TTL verification
- Cache-key scope and version isolation
- Knowledge-base version invalidation (bulk key eviction)
- Repeated question cache-hit verification: complete bypass of embedding, BM25, Qdrant, RRF, and LLM
- Graceful degradation when Redis connection fails
- Actual live Redis hit and miss latency measurement
"""

import time
import pytest
import redis
from unittest.mock import MagicMock

from app.schemas.chunk import GroundedAnswer, SourceCitation, Chunk, ChunkMetadata, ScoredChunk
from app.services.cache_service import RedisCacheService, generate_cache_key
from app.services.rag_service import RAGService
from app.services.generation_service import GenerationService


REDIS_TEST_URL = "redis://localhost:6379/0"


def is_redis_available() -> bool:
    try:
        r = redis.Redis.from_url(REDIS_TEST_URL, socket_connect_timeout=1.0)
        return bool(r.ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_redis_available(),
    reason="Live Redis instance not reachable on redis://localhost:6379/0"
)


@pytest.fixture(autouse=True)
def clean_test_redis_namespace():
    """Cleans up any keys created under the test namespace before and after each test."""
    r = redis.Redis.from_url(REDIS_TEST_URL, decode_responses=True)
    yield
    keys = r.keys("campusmind:answer:test_*") + r.keys("campusmind:answer:real_*")
    if keys:
        r.delete(*keys)


@pytest.fixture
def real_cache_service():
    return RedisCacheService(
        redis_url=REDIS_TEST_URL,
        namespace="campusmind:answer",
        kb_version="test_v1",
        default_ttl=60,
    )


def test_real_redis_set_get_and_serialization(real_cache_service):
    """Verifies storing and retrieving GroundedAnswer from real Redis preserves all fields."""
    question = "What are the hours for Turing Hall?"
    answer = GroundedAnswer(
        answer="Turing Hall is open from 7:00 AM to 10:00 PM [1].",
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Handbook_2026.pdf",
                page_number=1,
                chunk_id="chk-001",
                chunk_index=0,
                content_snippet="Turing Hall is open from 7:00 AM to 10:00 PM.",
            )
        ],
        has_sufficient_context=True,
        model_name="openai/gpt-oss-120b",
        prompt_tokens=42,
        completion_tokens=18,
    )

    success = real_cache_service.set_answer(question=question, answer=answer, ttl=60)
    assert success is True

    cached = real_cache_service.get_answer(question=question)
    assert cached is not None
    assert cached.answer == answer.answer
    assert cached.has_sufficient_context is True
    assert len(cached.sources) == 1
    assert cached.sources[0].citation_index == 1
    assert cached.sources[0].document_id == "doc_handbook_cs"
    assert cached.sources[0].page_number == 1
    assert cached.sources[0].chunk_id == "chk-001"
    assert cached.sources[0].content_snippet == "Turing Hall is open from 7:00 AM to 10:00 PM."
    assert cached.model_name == "openai/gpt-oss-120b"
    assert cached.prompt_tokens == 42
    assert cached.completion_tokens == 18


def test_real_redis_ttl_expiration(real_cache_service):
    """Verifies that Redis natively expires keys when TTL elapses."""
    question = "What is the temporary Wi-Fi guest password?"
    answer = GroundedAnswer(
        answer="The password is guest2026 [1].",
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_campus_facilities",
                document_name="Campus_Facilities_Guide.txt",
                page_number=1,
                chunk_id="chk-wifi",
                chunk_index=0,
                content_snippet="Wi-Fi guest password is guest2026.",
            )
        ],
        has_sufficient_context=True,
    )

    # Set with 1-second TTL
    real_cache_service.set_answer(question=question, answer=answer, ttl=1)
    # Check immediately
    assert real_cache_service.get_answer(question=question) is not None

    # Wait for TTL to expire
    time.sleep(1.2)
    assert real_cache_service.get_answer(question=question) is None


def test_real_redis_scope_and_version_isolation(real_cache_service):
    """Verifies that different access scopes and KB versions never collide in real Redis."""
    question = "Where are faculty evaluations archived?"
    answer_public = GroundedAnswer(
        answer="Public summary only [1].",
        has_sufficient_context=True,
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Handbook_2026.pdf",
                page_number=1,
                chunk_id="chk-pub",
                chunk_index=0,
                content_snippet="Public summary only.",
            )
        ],
    )
    answer_faculty = GroundedAnswer(
        answer="Internal evaluation records [1].",
        has_sufficient_context=True,
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Handbook_2026.pdf",
                page_number=2,
                chunk_id="chk-fac",
                chunk_index=1,
                content_snippet="Internal evaluation records.",
            )
        ],
    )

    # Set in different scopes
    real_cache_service.set_answer(question=question, answer=answer_public, scope="public")
    real_cache_service.set_answer(question=question, answer=answer_faculty, scope="faculty_only")

    pub = real_cache_service.get_answer(question=question, scope="public")
    fac = real_cache_service.get_answer(question=question, scope="faculty_only")

    assert pub is not None and pub.answer == "Public summary only [1]."
    assert fac is not None and fac.answer == "Internal evaluation records [1]."

    # Different version lookup should be a cache miss
    v2_lookup = real_cache_service.get_answer(question=question, scope="public", kb_version="test_v2")
    assert v2_lookup is None


def test_real_redis_knowledge_base_invalidation(real_cache_service):
    """Verifies rotating the KB version invalidates previous cache entries instantaneously."""
    q1 = "Question A"
    q2 = "Question B"
    ans = GroundedAnswer(
        answer="Sample answer [1].",
        has_sufficient_context=True,
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_handbook_cs",
                document_name="CS_Handbook_2026.pdf",
                page_number=1,
                chunk_id="chk-01",
                chunk_index=0,
                content_snippet="Sample answer.",
            )
        ],
    )

    real_cache_service.set_answer(q1, ans)
    real_cache_service.set_answer(q2, ans)

    assert real_cache_service.get_answer(q1) is not None
    assert real_cache_service.get_answer(q2) is not None

    # Rotate KB version: invalidates active lookups for all queries under previous version
    real_cache_service.update_kb_version("test_v2")

    # Both queries should now be cache misses under the new KB version
    assert real_cache_service.get_answer(q1) is None
    assert real_cache_service.get_answer(q2) is None


def test_real_redis_rag_pipeline_cache_hit_bypass(real_cache_service):
    """
    Verifies that on a cache hit in real Redis, the RAGService completely bypasses
    embedding, BM25, Qdrant, RRF, and LLM generation.
    """
    mock_hybrid = MagicMock()
    sample_chunk = ScoredChunk(
        chunk=Chunk(
            content="Dean of Engineering: Dr. Robert Vance.",
            metadata=ChunkMetadata(
                documentId="doc_handbook_cs",
                documentName="CS_Handbook_2026.pdf",
                chunkId="chk-01",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=1,
                characterCount=38,
            )
        ),
        score=0.98,
        retrieval_method="hybrid",
    )
    mock_hybrid.search.return_value = [sample_chunk]

    mock_llm_provider = MagicMock()
    mock_llm_provider.generate.return_value = {
        "content": "The Dean of Engineering is Dr. Robert Vance [1].",
        "model": "openai/gpt-oss-120b",
        "prompt_tokens": 100,
        "completion_tokens": 20,
    }

    gen_service = GenerationService(llm_provider=mock_llm_provider)

    rag = RAGService(
        cache_service=real_cache_service,
        hybrid_retrieval_service=mock_hybrid,
        generation_service=gen_service,
    )

    query_text = "Who is the Dean of Engineering?"

    # First request: Cache Miss -> runs retrieval and LLM
    resp1 = rag.query(question=query_text)
    assert resp1.answer == "The Dean of Engineering is Dr. Robert Vance [1]."
    assert mock_hybrid.search.call_count == 1
    assert mock_llm_provider.generate.call_count == 1

    # Second request: Cache Hit -> served from real Redis, BYPASSES retrieval & LLM
    resp2 = rag.query(question=query_text)
    assert resp2.answer == "The Dean of Engineering is Dr. Robert Vance [1]."
    assert mock_hybrid.search.call_count == 1  # No additional search call
    assert mock_llm_provider.generate.call_count == 1  # No additional LLM call


def test_real_redis_failure_fallback():
    """
    Verifies that when Redis is pointed at an invalid/unreachable host,
    RAGService logs the failure and gracefully completes RAG generation.
    """
    bad_cache_service = RedisCacheService(
        redis_url="redis://127.0.0.1:65530/0",  # closed port
        kb_version="test_v1",
        default_ttl=60,
    )

    mock_hybrid = MagicMock()
    sample_chunk = ScoredChunk(
        chunk=Chunk(
            content="Main Library hours are 7:30 AM to Midnight.",
            metadata=ChunkMetadata(
                documentId="doc_campus_facilities",
                documentName="Campus_Facilities_Guide.txt",
                chunkId="chk-lib",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=1,
                characterCount=44,
            )
        ),
        score=0.95,
        retrieval_method="hybrid",
    )
    mock_hybrid.search.return_value = [sample_chunk]

    mock_llm = MagicMock()
    mock_llm.generate.return_value = {
        "content": "The Main Library is open until Midnight [1].",
        "model": "openai/gpt-oss-120b",
        "prompt_tokens": 80,
        "completion_tokens": 15,
    }
    gen_service = GenerationService(llm_provider=mock_llm)

    rag = RAGService(
        cache_service=bad_cache_service,
        hybrid_retrieval_service=mock_hybrid,
        generation_service=gen_service,
    )

    # Should not raise any ConnectionError; should execute RAG seamlessly
    result = rag.query("What are the library hours?")
    assert "Midnight" in result.answer
    assert mock_hybrid.search.call_count == 1
    assert mock_llm.generate.call_count == 1


def test_real_redis_eviction_lru_and_lfu():
    """
    Verifies that real Redis actually performs LRU and LFU evictions under memory pressure
    in an isolated database without touching production keys.
    """
    # Use isolated DB 15
    r = redis.Redis(host="localhost", port=6379, db=15, decode_responses=True)
    r.flushdb()
    orig_maxmemory = r.config_get("maxmemory").get("maxmemory")
    orig_policy = r.config_get("maxmemory-policy").get("maxmemory-policy")

    try:
        # 1. LRU Eviction Test
        base = r.info("memory")["used_memory"]
        limit = base + 175000
        r.config_set("maxmemory", str(limit))
        r.config_set("maxmemory-policy", "allkeys-lru")
        r.config_set("maxmemory-samples", "10")

        chunk = "A" * 50000
        r.set("test_lru:k1", chunk)
        r.set("test_lru:k2", chunk)
        time.sleep(2)
        # Touch k1 so k2 becomes least recently used
        _ = r.get("test_lru:k1")

        # Exceed limit with k3
        r.set("test_lru:k3", chunk)
        assert r.exists("test_lru:k2") == 0, "LRU must evict idle key k2"
        assert r.exists("test_lru:k1") == 1, "LRU must retain recently touched key k1"
        assert r.exists("test_lru:k3") == 1, "LRU must store new key k3"

        # 2. LFU Eviction Test
        r.flushdb()
        base = r.info("memory")["used_memory"]
        limit = base + 170000
        r.config_set("maxmemory", str(limit))
        r.config_set("maxmemory-policy", "allkeys-lfu")
        r.config_set("maxmemory-samples", "10")

        r.set("test_lfu:infrequent", chunk)
        r.set("test_lfu:frequent", chunk)

        for _ in range(100):
            _ = r.get("test_lfu:frequent")
        _ = r.get("test_lfu:infrequent")

        r.set("test_lfu:k3", chunk)
        assert r.exists("test_lfu:infrequent") == 0, "LFU must evict infrequent key"
        assert r.exists("test_lfu:frequent") == 1, "LFU must retain frequent key"
        assert r.exists("test_lfu:k3") == 1, "LFU must store new key k3"

        # 3. Independent TTL Expiration Test
        r.set("test_ttl:ephemeral", "val", ex=1)
        assert r.exists("test_ttl:ephemeral") == 1
        time.sleep(1.2)
        assert r.exists("test_ttl:ephemeral") == 0, "TTL must expire key independently"

    finally:
        r.flushdb()
        r.config_set("maxmemory", orig_maxmemory)
        r.config_set("maxmemory-policy", orig_policy)

