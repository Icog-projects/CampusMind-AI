"""CampusMind AI - Vector Store Service.

Manages dense vector storage, payload indexing, and similarity retrieval in Qdrant.
"""

import os
import uuid
import logging
from typing import List, Optional, Dict, Any, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

from app.schemas.chunk import Chunk, ChunkMetadata, EmbeddedChunk, ScoredChunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "campusmind_chunks"
VECTOR_DIMENSION = 384


def chunk_id_to_uuid(chunk_id: str) -> str:
    """
    Converts a chunk_id string into a stable UUID string format required by Qdrant.
    If chunk_id is already a valid UUID, returns it directly; otherwise generates a deterministic UUIDv5.
    """
    try:
        val = uuid.UUID(chunk_id)
        return str(val)
    except (ValueError, AttributeError):
        # Generate deterministic UUID using DNS namespace
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(chunk_id)))


class VectorStoreService:
    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        prefer_grpc: bool = False,
        client: Optional[QdrantClient] = None,
    ):
        """
        Initializes the VectorStoreService.
        
        Args:
            collection_name: Name of the Qdrant collection (default: 'campusmind_chunks').
            url: Qdrant server URL (e.g. 'http://localhost:6333') or None for in-memory / env var.
            api_key: Optional API key for remote Qdrant instances.
            prefer_grpc: Whether to use gRPC protocol for remote connections.
            client: Optional pre-configured QdrantClient instance (for testing).
        """
        self.collection_name = collection_name
        self.vector_dimension = VECTOR_DIMENSION

        if client is not None:
            self._client = client
        else:
            qdrant_url = url or os.getenv("QDRANT_URL")
            qdrant_key = api_key or os.getenv("QDRANT_API_KEY")

            if qdrant_url:
                logger.info("Connecting to Qdrant server at: %s", qdrant_url)
                self._client = QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_key,
                    prefer_grpc=prefer_grpc,
                )
            else:
                logger.info("Initializing in-memory QdrantClient (':memory:').")
                self._client = QdrantClient(":memory:")

    @property
    def client(self) -> QdrantClient:
        return self._client

    def ensure_collection(self) -> bool:
        """
        Verifies if the target collection exists. If not, creates it with
        dimension=384 and distance=COSINE.
        
        Returns:
            True if collection exists or was successfully created.
        """
        try:
            collections = self._client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info("Creating Qdrant collection: %s (size=%d, distance=Cosine)", self.collection_name, self.vector_dimension)
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest.VectorParams(
                        size=self.vector_dimension,
                        distance=rest.Distance.COSINE,
                    ),
                )
            return True
        except Exception as e:
            logger.error("Failed to ensure collection '%s': %s", self.collection_name, str(e))
            raise RuntimeError(f"Qdrant collection initialization failed: {e}") from e

    def upsert_chunks(self, embedded_chunks: Sequence[EmbeddedChunk], batch_size: int = 64) -> int:
        """
        Batch upserts EmbeddedChunk objects into Qdrant.
        Stores chunk content and complete metadata in the point payload.
        
        Args:
            embedded_chunks: Sequence of EmbeddedChunk items.
            batch_size: Batch size for chunk upsertion.
            
        Returns:
            Number of chunks upserted.
        """
        if not embedded_chunks:
            return 0

        self.ensure_collection()

        points: List[rest.PointStruct] = []
        for idx, item in enumerate(embedded_chunks):
            if not isinstance(item, EmbeddedChunk):
                raise TypeError(f"Item at index {idx} must be an EmbeddedChunk, got {type(item)}")

            # Validate vector dimensions
            if len(item.embedding) != self.vector_dimension:
                raise ValueError(
                    f"Vector dimension mismatch at index {idx}: expected {self.vector_dimension}, got {len(item.embedding)}"
                )

            chunk = item.chunk
            point_id = chunk_id_to_uuid(chunk.metadata.chunk_id)

            payload = {
                "content": chunk.content,
                "documentId": chunk.metadata.document_id,
                "documentName": chunk.metadata.document_name,
                "chunkId": chunk.metadata.chunk_id,
                "chunkIndex": chunk.metadata.chunk_index,
                "chunkingMethod": chunk.metadata.chunking_method,
                "pageNumber": chunk.metadata.page_number,
                "tokenCountApprox": chunk.metadata.token_count_approx,
                "characterCount": chunk.metadata.character_count,
            }

            points.append(
                rest.PointStruct(
                    id=point_id,
                    vector=item.embedding,
                    payload=payload,
                )
            )

        # Batch upsert into Qdrant
        total_upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )
            total_upserted += len(batch)

        logger.info("Successfully upserted %d points into '%s'.", total_upserted, self.collection_name)
        return total_upserted

    def search(
        self,
        query_vector: Sequence[float],
        top_k: int = 5,
        filter_document_id: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[ScoredChunk]:
        """
        Performs dense vector similarity search against the Qdrant collection.
        
        Args:
            query_vector: 384-dimensional dense vector representing the search query.
            top_k: Number of nearest neighbors to retrieve (must be >= 1).
            filter_document_id: Optional documentId filter.
            min_score: Minimum cosine similarity score.
            
        Returns:
            List of ScoredChunk objects with retrieval_method='vector'.
        """
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")

        if not query_vector:
            raise ValueError("query_vector cannot be empty.")

        if len(query_vector) != self.vector_dimension:
            raise ValueError(
                f"query_vector dimension mismatch: expected {self.vector_dimension}, got {len(query_vector)}"
            )

        self.ensure_collection()

        # Build optional Qdrant payload filter
        query_filter = None
        if filter_document_id:
            query_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="documentId",
                        match=rest.MatchValue(value=filter_document_id),
                    )
                ]
            )

        # Execute vector search
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
            score_threshold=min_score if min_score > 0.0 else None,
        )

        results: List[ScoredChunk] = []
        for scored_point in response.points:
            payload = scored_point.payload or {}
            content = payload.get("content", "")

            meta = ChunkMetadata(
                documentId=payload.get("documentId", "unknown"),
                documentName=payload.get("documentName", "unknown"),
                chunkId=payload.get("chunkId", str(scored_point.id)),
                chunkIndex=payload.get("chunkIndex", 0),
                chunkingMethod=payload.get("chunkingMethod", "unknown"),
                pageNumber=payload.get("pageNumber"),
                tokenCountApprox=payload.get("tokenCountApprox"),
                characterCount=payload.get("characterCount", len(content)),
            )

            chunk = Chunk(content=content, metadata=meta)
            results.append(
                ScoredChunk(
                    chunk=chunk,
                    score=float(scored_point.score),
                    retrieval_method="vector",
                )
            )

        return results

    def delete_document(self, document_id: str) -> bool:
        """
        Deletes all chunks associated with a specific documentId.
        
        Args:
            document_id: ID of the document whose chunks should be deleted.
            
        Returns:
            True if deletion request succeeded.
        """
        if not document_id:
            raise ValueError("document_id cannot be empty.")

        self.ensure_collection()

        filter_condition = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="documentId",
                    match=rest.MatchValue(value=document_id),
                )
            ]
        )

        self._client.delete(
            collection_name=self.collection_name,
            points_selector=filter_condition,
            wait=True,
        )
        logger.info("Deleted chunks for documentId '%s' from '%s'.", document_id, self.collection_name)
        return True

    def count_chunks(self) -> int:
        """Returns the number of points in the collection."""
        self.ensure_collection()
        res = self._client.count(collection_name=self.collection_name, exact=True)
        return res.count
