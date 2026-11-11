"""CampusMind AI - Redis Answer Cache Service.

Provides deterministic caching, TTL expiration, and configurable eviction policies (LRU/LFU).

Responsibilities:
1. normalize_question(): Standardizes question strings by lowercasing and trimming whitespace.
2. generate_cache_key(): Builds a deterministic SHA-256 cache key from normalized query, version, and scope.
Class RedisCacheService:
3. RedisCacheService.__init__(): Initializes cache configuration, TTL, and memory eviction settings.
4. RedisCacheService.client(): Connects or returns active Redis client instance.
5. RedisCacheService.configure_eviction_policy(): Configures maxmemory and eviction policy (allkeys-lru or allkeys-lfu).
6. RedisCacheService.get_cache_info(): Retrieves live Redis memory stats, active policy, and configured limits.
7. RedisCacheService.get_answer(): Retrieves cached grounded answer if present.
8. RedisCacheService.set_answer(): Stores serialized grounded answer with TTL into Redis.
9. RedisCacheService.get_answer_by_key(): Retrieves cached grounded answer directly by its Redis cache key.
10. RedisCacheService.update_kb_version(): Updates knowledge-base version to invalidate prior cache entries.
11. RedisCacheService.delete_scope_answer(): Deletes specific cached answer entry by query and scope.
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
DEFAULT_MAXMEMORY = "100mb"
DEFAULT_EVICTION_POLICY = "allkeys-lru"


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

    # Initializes cache configuration, TTL, and memory eviction settings.
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = DEFAULT_CACHE_TTL,
        kb_version: str = DEFAULT_KB_VERSION,
        namespace: str = DEFAULT_REDIS_NAMESPACE,
        client: Optional[Any] = None,
        maxmemory: Optional[str] = None,
        eviction_policy: Optional[str] = None,
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

        self.maxmemory = maxmemory or os.getenv("REDIS_MAXMEMORY", DEFAULT_MAXMEMORY)
        self.eviction_policy = eviction_policy or os.getenv("REDIS_EVICTION_POLICY", DEFAULT_EVICTION_POLICY)
        self._configured_policy = False

    # Lazy-initializes or returns the active Redis client connection.
    @property
    def client(self) -> Optional[Any]:
        if self._client is not None:
            if not self._configured_policy and hasattr(self._client, "config_set"):
                self.configure_eviction_policy(policy=self.eviction_policy, maxmemory=self.maxmemory)
            return self._client

        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            self.configure_eviction_policy(policy=self.eviction_policy, maxmemory=self.maxmemory)
            return self._client
        except Exception as e:
            logger.warning("Failed to initialize Redis client (%s): %s", self.redis_url, e)
            return None

    # Configures Redis maxmemory limit and eviction policy (allkeys-lru or allkeys-lfu).
    def configure_eviction_policy(self, policy: str, maxmemory: Optional[str] = None) -> bool:
        if self._client is None:
            return False

        clean_policy = policy.strip().lower()
        if clean_policy not in ["allkeys-lru", "allkeys-lfu", "volatile-lru", "volatile-lfu", "noeviction"]:
            raise ValueError(f"Unsupported eviction policy: '{policy}'. Supported: allkeys-lru, allkeys-lfu")

        mem = maxmemory or self.maxmemory
        try:
            if mem and hasattr(self._client, "config_set"):
                self._client.config_set("maxmemory", mem)
            if hasattr(self._client, "config_set"):
                self._client.config_set("maxmemory-policy", clean_policy)
            self.eviction_policy = clean_policy
            self.maxmemory = mem
            self._configured_policy = True
            logger.info("Configured Redis maxmemory=%s, policy=%s", mem, clean_policy)
            return True
        except Exception as e:
            logger.warning("Could not set Redis configuration: %s", e)
            return False

    # Retrieves live Redis memory stats, active policy, and configured limits.
    def get_cache_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "ttl_seconds": self.default_ttl,
            "configured_maxmemory": self.maxmemory,
            "configured_policy": self.eviction_policy,
            "connected": False,
            "used_memory_human": "N/A",
            "maxmemory_human": "N/A",
            "live_policy": self.eviction_policy,
        }

        cli = self.client
        if cli is None:
            return info

        try:
            mem_info = cli.info("memory")
            info["connected"] = True
            info["used_memory_human"] = mem_info.get("used_memory_human", "N/A")
            info["maxmemory_human"] = mem_info.get("maxmemory_human", "N/A")
            
            cfg_policy = cli.config_get("maxmemory-policy")
            if isinstance(cfg_policy, dict):
                info["live_policy"] = cfg_policy.get("maxmemory-policy", self.eviction_policy)
            cfg_mem = cli.config_get("maxmemory")
            if isinstance(cfg_mem, dict) and cfg_mem.get("maxmemory"):
                val = cfg_mem.get("maxmemory")
                if val != "0" and info["maxmemory_human"] == "N/A":
                    info["maxmemory_human"] = f"{int(val) // (1024*1024)}M"
        except Exception as e:
            logger.warning("Failed to query Redis memory info: %s", e)

        return info

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

    # Retrieves a cached GroundedAnswer directly by its Redis cache key.
    def get_answer_by_key(self, cache_key: str) -> Optional[GroundedAnswer]:
        if not cache_key:
            return None
        cli = self.client
        if cli is None:
            return None
        try:
            cached_data = cli.get(cache_key)
            if not cached_data:
                return None
            payload = json.loads(cached_data)
            answer = GroundedAnswer.model_validate(payload)
            logger.info("Cache hit for direct key: %s", cache_key)
            return answer
        except Exception as e:
            logger.warning("Redis get error for direct key %s: %s", cache_key, e)
            return None

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
