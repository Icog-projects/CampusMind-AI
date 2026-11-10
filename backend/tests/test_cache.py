"""
Tests for Redis Answer Cache Service in CampusMind AI.

Verifies:
1. Deterministic cache key generation with SHA-256 and question normalization.
2. Knowledge base version changes produce distinct keys.
3. Access scopes produce distinct keys.
4. Setting and getting a GroundedAnswer with full JSON serialization.
5. TTL configuration and enforcement.
6. Skipping cache for answers without sufficient context or sources.
7. Handling of corrupted or invalid cached JSON data.
8. Graceful degradation when Redis client raises connection or command errors.
"""

import json
import pytest
from unittest.mock import MagicMock

from app.schemas.chunk import GroundedAnswer, SourceCitation
from app.services.cache_service import (
    RedisCacheService,
    normalize_question,
    generate_cache_key,
    DEFAULT_CACHE_TTL,
)


def sample_grounded_answer(has_context: bool = True) -> GroundedAnswer:
    citations = []
    if has_context:
        citations = [
            SourceCitation(
                citation_index=1,
                document_id="doc-123",
                document_name="Syllabus.pdf",
                page_number=4,
                chunk_id="chunk-99",
                chunk_index=2,
                content_snippet="Final exams account for 40% of the grade.",
            )
        ]
    return GroundedAnswer(
        answer="Final exams are 40% of the grade [1]." if has_context else "Insufficient information.",
        sources=citations,
        has_sufficient_context=has_context,
        model_name="openai/gpt-oss-120b",
        prompt_tokens=150,
        completion_tokens=25,
    )


def test_question_normalization():
    """Verify that case and redundant whitespace do not alter the normalized question."""
    q1 = "What is the grading policy?"
    q2 = "  what   is   THE   grading   policy?  "
    assert normalize_question(q1) == normalize_question(q2)


def test_deterministic_cache_key_generation():
    """Verify cache keys are deterministic SHA-256 hashes with namespace, version, and scope."""
    key1 = generate_cache_key("Where is the library?", kb_version="v1", scope="public")
    key2 = generate_cache_key("where is the library?", kb_version="v1", scope="public")
    assert key1 == key2
    assert key1.startswith("campusmind:answer:v1:public:")
    assert len(key1.split(":")[-1]) == 64  # SHA-256 hex string length


def test_different_versions_produce_different_keys():
    """Verify modifying kb_version changes the cache key."""
    key_v1 = generate_cache_key("When does class start?", kb_version="v1", scope="public")
    key_v2 = generate_cache_key("When does class start?", kb_version="v2", scope="public")
    assert key_v1 != key_v2


def test_different_scopes_produce_different_keys():
    """Verify different access scopes produce distinct cache keys."""
    key_public = generate_cache_key("Course prerequisites", kb_version="v1", scope="public")
    key_faculty = generate_cache_key("Course prerequisites", kb_version="v1", scope="faculty")
    assert key_public != key_faculty


def test_cache_set_and_get_success():
    """Verify storing and retrieving a GroundedAnswer from Redis with JSON serialization."""
    mock_redis = MagicMock()
    stored_data = {}

    def mock_set(name, value, ex):
        stored_data[name] = value
        return True

    def mock_get(name):
        return stored_data.get(name)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    cache_service = RedisCacheService(client=mock_redis, default_ttl=1200)

    original_answer = sample_grounded_answer(has_context=True)
    question = "What is the grading policy?"

    # Set answer
    success = cache_service.set_answer(question=question, answer=original_answer, scope="public")
    assert success is True
    assert mock_redis.set.called
    assert mock_redis.set.call_args[1]["ex"] == 1200

    # Get answer
    retrieved = cache_service.get_answer(question=question, scope="public")
    assert retrieved is not None
    assert retrieved.answer == original_answer.answer
    assert retrieved.has_sufficient_context is True
    assert len(retrieved.sources) == 1
    assert retrieved.sources[0].document_name == "Syllabus.pdf"
    assert retrieved.sources[0].page_number == 4


def test_do_not_cache_insufficient_context_answers():
    """Verify answers marked with has_sufficient_context=False are not cached."""
    mock_redis = MagicMock()
    cache_service = RedisCacheService(client=mock_redis)

    insufficient_answer = sample_grounded_answer(has_context=False)
    success = cache_service.set_answer("Unknown question", insufficient_answer)

    assert success is False
    assert not mock_redis.set.called


def test_corrupted_cached_data_handled_safely():
    """Verify that corrupt JSON in Redis returns None rather than crashing."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = "{invalid_json: 123"

    cache_service = RedisCacheService(client=mock_redis)
    result = cache_service.get_answer("Any query")
    assert result is None


def test_redis_connection_error_fallback():
    """Verify Redis exceptions degrade gracefully to None/False without crashing."""
    mock_redis = MagicMock()
    mock_redis.get.side_effect = Exception("ConnectionRefusedError")
    mock_redis.set.side_effect = Exception("ConnectionRefusedError")

    cache_service = RedisCacheService(client=mock_redis)

    # Get should return None
    assert cache_service.get_answer("Query with failed Redis") is None

    # Set should return False
    valid_answer = sample_grounded_answer(has_context=True)
    assert cache_service.set_answer("Query with failed Redis", valid_answer) is False


def test_kb_version_invalidation():
    """Verify updating the kb_version invalidates subsequent lookups."""
    mock_redis = MagicMock()
    store = {}

    def mock_set(name, value, ex=None):
        store[name] = value
        return True

    def mock_get(name):
        return store.get(name)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    cache_service = RedisCacheService(client=mock_redis, kb_version="v1")
    answer = sample_grounded_answer(has_context=True)
    q = "Where is room 101?"

    cache_service.set_answer(q, answer)
    assert cache_service.get_answer(q) is not None

    # Update version to v2
    cache_service.update_kb_version("v2")
    # Now it looks for key with v2, which does not exist in store -> cache miss
    assert cache_service.get_answer(q) is None
