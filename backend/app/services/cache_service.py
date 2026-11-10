"""CampusMind AI - Redis Answer Cache Service.

Provides deterministic caching and invalidation of grounded answers using Redis.
"""

import os
import json
import hashlib
import logging
from typing import Optional, Any, Dict

from dotenv import load_dotenv

from app.schemas.chunk import GroundedAnswer

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_REDIS_NAMESPACE = "campusmind:answer"
DEFAULT_CACHE_TTL = 1800  # 30 minutes
DEFAULT_KB_VERSION = "v1"
DEFAULT_ACCESS_SCOPE = "public"


def normalize_question(question: str) -> str:
    """
    Normalizes question text for consistent cache key generation:
    strips leading/trailing whitespace, converts to lowercase, and collapses extra internal whitespace.
    """
    if not question:
        return ""
    return " ".join(question.strip().lower().split())


def generate_cache_key(
    question: str,
    kb_version: str = DEFAULT_KB_VERSION,
    scope: str = DEFAULT_ACCESS_SCOPE,
    namespace: str = DEFAULT_REDIS_NAMESPACE,
) -> str:
    """
    Generates a deterministic Redis cache key.

    Formula:
        {namespace}:{kb_version}:{scope}:{sha256(normalized_question)}

    Args:
        question: User query string.
        kb_version: Knowledge-base version string (e.g. 'v1', 'v2026-11').
        scope: Access context / permission tier (e.g. 'public', 'course_cs101').
        namespace: Cache key prefix.

    Returns:
        Structured cache key string.
    """
    normalized = normalize_question(question)
    query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    clean_version = kb_version.strip() if kb_version else DEFAULT_KB_VERSION
    clean_scope = scope.strip() if scope else DEFAULT_ACCESS_SCOPE
    clean_ns = namespace.strip() if namespace else DEFAULT_REDIS_NAMESPACE

    return f"{clean_ns}:{clean_version}:{clean_scope}:{query_hash}"


class RedisCacheService:
    """
    Manages caching and retrieval of GroundedAnswer objects in Redis.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = DEFAULT_CACHE_TTL,
        kb_version: str = DEFAULT_KB_VERSION,
        namespace: str = DEFAULT_REDIS_NAMESPACE,
        client: Optional[Any] = None,
    ):
        """
        Initializes the cache service.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL from env).
            default_ttl: Expiration TTL in seconds (defaults to REDIS_CACHE_TTL or 1800s).
            kb_version: Current knowledge-base version.
            namespace: Namespace prefix for Redis keys.
            client: Optional pre-configured Redis client (used for dependency injection & testing).
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Prioritize explicit constructor default_ttl if provided, otherwise check env
        if default_ttl != DEFAULT_CACHE_TTL:
            self.default_ttl = default_ttl
        else:
            env_ttl = os.getenv("REDIS_CACHE_TTL")
            self.default_ttl = int(env_ttl) if env_ttl and env_ttl.isdigit() else default_ttl

        self.kb_version = kb_version
        self.namespace = namespace
        self._client = client
        self._is_connected: Optional[bool] = None

    @property
    def client(self) -> Optional[Any]:
        """Lazy-initializes or returns the Redis client connection."""
        if self._client is not None:
            return self._client

        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            return self._client
        except Exception as e:
            logger.warning("Failed to initialize Redis client (%s): %s", self.redis_url, e)
            return None

    def get_answer(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
    ) -> Optional[GroundedAnswer]:
        """
        Retrieves a cached GroundedAnswer for a question if present and valid.

        Args:
            question: User question string.
            scope: Access scope.
            kb_version: Optional override for knowledge-base version.

        Returns:
            GroundedAnswer if cache hit, else None.
        """
        if not question or not question.strip():
            return None

        version = kb_version or self.kb_version
        cache_key = generate_cache_key(
            question=question,
            kb_version=version,
            scope=scope,
            namespace=self.namespace,
        )

        cli = self.client
        if cli is None:
            return None

        try:
            cached_data = cli.get(cache_key)
            if not cached_data:
                return None

            payload = json.loads(cached_data)
            answer = GroundedAnswer.model_validate(payload)
            logger.info("Cache hit for key: %s", cache_key)
            return answer

        except Exception as e:
            logger.warning("Redis get error for key %s: %s", cache_key, e)
            return None

    def set_answer(
        self,
        question: str,
        answer: GroundedAnswer,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Caches a GroundedAnswer in Redis with expiration TTL.
        Only successful, grounded answers with sufficient context are recommended to be cached.

        Args:
            question: User question string.
            answer: GroundedAnswer instance to cache.
            scope: Access scope.
            kb_version: Optional override for knowledge-base version.
            ttl: Expiration in seconds (defaults to default_ttl).

        Returns:
            True if cached successfully, False otherwise.
        """
        if not question or not question.strip():
            return False

        if not isinstance(answer, GroundedAnswer):
            raise TypeError(f"Expected GroundedAnswer instance, got {type(answer)}")

        # Enforce requirement: cache only answers with sufficient context
        if not answer.has_sufficient_context:
            logger.debug("Skipping cache for answer without sufficient context.")
            return False

        version = kb_version or self.kb_version
        cache_key = generate_cache_key(
            question=question,
            kb_version=version,
            scope=scope,
            namespace=self.namespace,
        )

        cli = self.client
        if cli is None:
            return False

        expiration = ttl if ttl is not None and ttl > 0 else self.default_ttl

        try:
            serialized = answer.model_dump_json()
            cli.set(name=cache_key, value=serialized, ex=expiration)
            logger.info("Cached answer for key: %s (TTL: %ds)", cache_key, expiration)
            return True
        except Exception as e:
            logger.warning("Redis set error for key %s: %s", cache_key, e)
            return False

    def update_kb_version(self, new_version: str):
        """
        Updates the active knowledge base version.
        This provides instantaneous cache invalidation for all subsequent queries
        without issuing expensive mass deletion commands across Redis keys.
        """
        if not new_version or not new_version.strip():
            raise ValueError("Knowledge base version cannot be empty.")
        old = self.kb_version
        self.kb_version = new_version.strip()
        logger.info("Knowledge base version updated: %s -> %s (cache invalidated)", old, self.kb_version)

    def delete_scope_answer(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
    ) -> bool:
        """
        Deletes a specific cached answer by its key components.
        """
        version = kb_version or self.kb_version
        cache_key = generate_cache_key(
            question=question,
            kb_version=version,
            scope=scope,
            namespace=self.namespace,
        )
        cli = self.client
        if cli is None:
            return False
        try:
            cli.delete(cache_key)
            return True
        except Exception as e:
            logger.warning("Redis delete error for key %s: %s", cache_key, e)
            return False
