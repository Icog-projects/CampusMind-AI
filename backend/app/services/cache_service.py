"""CampusMind AI - Redis Answer Cache Service.

Provides deterministic caching and invalidation of grounded answers using Redis.

Responsibilities:
1. normalize_question(): Standardizes question strings by lowercasing and trimming whitespace.
2. generate_cache_key(): Builds a deterministic SHA-256 cache key from normalized query, version, and scope.
Class RedisCacheService:
3. RedisCacheService.__init__(): Initializes cache configuration and connection settings.
4. RedisCacheService.client(): Connects or returns active Redis client instance.
5. RedisCacheService.get_answer(): Retrieves cached grounded answer if present.
6. RedisCacheService.set_answer(): Stores serialized grounded answer with TTL into Redis.
7. RedisCacheService.update_kb_version(): Updates knowledge-base version to invalidate prior cache entries.
8. RedisCacheService.delete_scope_answer(): Deletes specific cached answer entry by query and scope.
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


# Normalizes question text for consistent cache key generation.
def normalize_question(question: str) -> str:
    if not question:
        return ""
    return " ".join(question.strip().lower().split())


# Generates a deterministic Redis cache key using question hash, KB version, and scope.
def generate_cache_key(
    question: str,
    kb_version: str = DEFAULT_KB_VERSION,
    scope: str = DEFAULT_ACCESS_SCOPE,
    namespace: str = DEFAULT_REDIS_NAMESPACE,
) -> str:
    normalized = normalize_question(question)
    query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    clean_version = kb_version.strip() if kb_version else DEFAULT_KB_VERSION
    clean_scope = scope.strip() if scope else DEFAULT_ACCESS_SCOPE
    clean_ns = namespace.strip() if namespace else DEFAULT_REDIS_NAMESPACE

    return f"{clean_ns}:{clean_version}:{clean_scope}:{query_hash}"


# Manages caching and retrieval of GroundedAnswer objects in Redis.
class RedisCacheService:

    # Initializes cache configuration and connection settings.
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = DEFAULT_CACHE_TTL,
        kb_version: str = DEFAULT_KB_VERSION,
        namespace: str = DEFAULT_REDIS_NAMESPACE,
        client: Optional[Any] = None,
    ):
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

    # Lazy-initializes or returns the active Redis client connection.
    @property
    def client(self) -> Optional[Any]:
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

    # Retrieves a cached GroundedAnswer for a question if present and valid.
    def get_answer(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
    ) -> Optional[GroundedAnswer]:
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

    # Caches a GroundedAnswer in Redis with expiration TTL.
    def set_answer(
        self,
        question: str,
        answer: GroundedAnswer,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
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

    # Updates the active knowledge-base version for instant cache invalidation.
    def update_kb_version(self, new_version: str):
        if not new_version or not new_version.strip():
            raise ValueError("Knowledge base version cannot be empty.")
        old = self.kb_version
        self.kb_version = new_version.strip()
        logger.info("Knowledge base version updated: %s -> %s (cache invalidated)", old, self.kb_version)

    # Deletes a specific cached answer by its key components.
    def delete_scope_answer(
        self,
        question: str,
        scope: str = DEFAULT_ACCESS_SCOPE,
        kb_version: Optional[str] = None,
    ) -> bool:
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
