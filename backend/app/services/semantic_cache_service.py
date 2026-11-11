"""CampusMind AI - Semantic Cache Service.

Provides vector-based semantic caching over previously generated, grounded answers
using a dedicated Qdrant collection ('campusmind_semantic_cache') linked to Redis cache keys.

Responsibilities:
Class SemanticCacheService:
1. SemanticCacheService.__init__(): Initializes configuration, similarity threshold, and collection name.
2. SemanticCacheService.ensure_collection(): Verifies existence of the semantic cache Qdrant collection or creates it.
3. SemanticCacheService.search_similar(): Searches for a matching cached question embedding within scope, kb_version, and similarity threshold.
4. SemanticCacheService.store(): Indexes the question embedding and its associated Redis cache key into Qdrant.
5. SemanticCacheService.count(): Returns total count of semantically cached queries in Qdrant.
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

logger = logging.getLogger(__name__)

DEFAULT_SEMANTIC_CACHE_COLLECTION = "campusmind_semantic_cache"
DEFAULT_SIMILARITY_THRESHOLD = 0.90
VECTOR_DIMENSION = 384


# Manages semantic similarity caching of questions using Qdrant and Redis keys.
class SemanticCacheService:

    # Initializes configuration, similarity threshold, and collection name.
    def __init__(
        self,
        collection_name: str = DEFAULT_SEMANTIC_CACHE_COLLECTION,
        similarity_threshold: Optional[float] = None,
        qdrant_client: Optional[QdrantClient] = None,
        vector_dimension: int = VECTOR_DIMENSION,
    ):
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension

        # Load threshold from argument or environment variable SEMANTIC_CACHE_THRESHOLD
        if similarity_threshold is not None:
            self.similarity_threshold = float(similarity_threshold)
        else:
            env_thresh = os.getenv("SEMANTIC_CACHE_THRESHOLD")
            self.similarity_threshold = float(env_thresh) if env_thresh else DEFAULT_SIMILARITY_THRESHOLD

        if qdrant_client is not None:
            self._client = qdrant_client
        else:
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_key = os.getenv("QDRANT_API_KEY")
            if qdrant_url:
                self._client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
            else:
                self._client = QdrantClient(":memory:")

        self._collection_ensured = False

    # Verifies existence of the semantic cache Qdrant collection or creates it.
    def ensure_collection(self) -> bool:
        if self._collection_ensured:
            return True

        try:
            collections = self._client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(
                    "Creating Qdrant semantic cache collection: %s (size=%d, distance=Cosine)",
                    self.collection_name,
                    self.vector_dimension,
                )
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest.VectorParams(
                        size=self.vector_dimension,
                        distance=rest.Distance.COSINE,
                    ),
                )
            self._collection_ensured = True
            return True
        except Exception as e:
            logger.error("Failed to ensure semantic cache collection '%s': %s", self.collection_name, e)
            return False

    # Searches for a matching cached question embedding within scope, kb_version, and similarity threshold.
    def search_similar(
        self,
        query_vector: Sequence[float],
        scope: str = "public",
        kb_version: str = "v1",
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        if not query_vector or len(query_vector) != self.vector_dimension:
            return None

        if not self.ensure_collection():
            return None

        min_score = threshold if threshold is not None else self.similarity_threshold

        # Filter strictly by access scope and knowledge-base version
        query_filter = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="scope",
                    match=rest.MatchValue(value=scope),
                ),
                rest.FieldCondition(
                    key="kb_version",
                    match=rest.MatchValue(value=kb_version),
                ),
            ]
        )

        try:
            response = self._client.query_points(
                collection_name=self.collection_name,
                query=list(query_vector),
                query_filter=query_filter,
                limit=1,
                with_payload=True,
                with_vectors=False,
                score_threshold=min_score,
            )

            if response.points:
                top_point = response.points[0]
                payload = top_point.payload or {}
                return {
                    "cache_key": payload.get("cache_key"),
                    "question": payload.get("question"),
                    "score": float(top_point.score),
                    "scope": payload.get("scope"),
                    "kb_version": payload.get("kb_version"),
                }
            return None
        except Exception as e:
            logger.warning("Error searching semantic cache collection: %s", e)
            return None

    # Indexes the question embedding and its associated Redis cache key into Qdrant.
    def store(
        self,
        question: str,
        query_vector: Sequence[float],
        cache_key: str,
        scope: str = "public",
        kb_version: str = "v1",
    ) -> bool:
        if not question or not query_vector or not cache_key:
            return False

        if len(query_vector) != self.vector_dimension:
            logger.warning("Query vector dimension %d != %d", len(query_vector), self.vector_dimension)
            return False

        if not self.ensure_collection():
            return False

        # Deterministic UUID per cache_key to prevent redundant duplicates
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, cache_key))

        payload = {
            "cache_key": cache_key,
            "question": question,
            "scope": scope,
            "kb_version": kb_version,
        }

        point = rest.PointStruct(
            id=point_id,
            vector=list(query_vector),
            payload=payload,
        )

        try:
            self._client.upsert(
                collection_name=self.collection_name,
                points=[point],
                wait=True,
            )
            logger.info("Stored semantic cache entry for key: %s (collection: %s)", cache_key, self.collection_name)
            return True
        except Exception as e:
            logger.warning("Failed to store semantic cache entry in Qdrant: %s", e)
            return False

    # Returns total count of semantically cached queries in Qdrant.
    def count(self) -> int:
        if not self.ensure_collection():
            return 0
        try:
            res = self._client.count(collection_name=self.collection_name, exact=True)
            return res.count
        except Exception as e:
            logger.warning("Failed to count semantic cache points: %s", e)
            return 0

