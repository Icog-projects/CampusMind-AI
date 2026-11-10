"""
Unit tests for Qdrant Vector Store Service in CampusMind AI.
Verifies:
- In-memory collection creation (dimension=384, COSINE distance).
- Batch upsert of EmbeddedChunk items.
- Cosine similarity vector search and ranking.
- Complete metadata and page-number preservation.
- Document-level deletion using documentId.
- Filtered search by documentId.
- Robust handling of invalid vector dimensions, empty inputs, and invalid top_k.
"""

import math
import uuid
import pytest
from qdrant_client import QdrantClient
from app.services.vector_store import VectorStoreService, chunk_id_to_uuid, VECTOR_DIMENSION
from app.schemas.chunk import Chunk, ChunkMetadata, EmbeddedChunk, ScoredChunk


def make_unit_vector(seed: int, dimension: int = VECTOR_DIMENSION) -> list[float]:
    """Generates a reproducible 384-dimensional unit vector."""
    vec = [(math.sin(seed * (i + 1))) for i in range(dimension)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


@pytest.fixture
def in_memory_vector_store():
    """Initializes an isolated in-memory Qdrant instance for each test."""
    service = VectorStoreService(collection_name="test_collection", client=QdrantClient(":memory:"))
    service.ensure_collection()
    return service


@pytest.fixture
def sample_embedded_chunks():
    """Builds sample embedded chunks across distinct documents and topics."""
    chunks = []
    # Document 1: Operating Systems
    v1 = make_unit_vector(seed=1)
    chunks.append(
        EmbeddedChunk(
            chunk=Chunk(
                content="Virtual memory allows execution of processes that are not completely in memory.",
                metadata=ChunkMetadata(
                    documentId="doc_os",
                    documentName="os_overview.pdf",
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=0,
                    chunkingMethod="recursive",
                    pageNumber=3,
                    characterCount=78,
                    tokenCountApprox=12,
                ),
            ),
            embedding=v1,
        )
    )

    v2 = make_unit_vector(seed=2)
    chunks.append(
        EmbeddedChunk(
            chunk=Chunk(
                content="Round robin scheduling allocates equal CPU time slices to each process.",
                metadata=ChunkMetadata(
                    documentId="doc_os",
                    documentName="os_overview.pdf",
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=1,
                    chunkingMethod="recursive",
                    pageNumber=5,
                    characterCount=72,
                    tokenCountApprox=11,
                ),
            ),
            embedding=v2,
        )
    )

    # Document 2: Databases
    v3 = make_unit_vector(seed=10)
    chunks.append(
        EmbeddedChunk(
            chunk=Chunk(
                content="B-tree indices minimize disk I/O operations for large database tables.",
                metadata=ChunkMetadata(
                    documentId="doc_db",
                    documentName="db_systems.pdf",
                    chunkId=str(uuid.uuid4()),
                    chunkIndex=0,
                    chunkingMethod="recursive",
                    pageNumber=18,
                    characterCount=70,
                    tokenCountApprox=12,
                ),
            ),
            embedding=v3,
        )
    )

    return chunks


def test_chunk_id_to_uuid_stability():
    """Verify deterministic and valid UUID conversion for arbitrary chunk IDs."""
    test_id = "chunk_string_abc_123"
    uuid_str = chunk_id_to_uuid(test_id)
    # Check that it's a valid UUID
    parsed = uuid.UUID(uuid_str)
    assert str(parsed) == uuid_str
    # Check determinism: same input produces same UUID
    assert chunk_id_to_uuid(test_id) == uuid_str

    # Valid UUID string remains unchanged
    existing_uuid = str(uuid.uuid4())
    assert chunk_id_to_uuid(existing_uuid) == existing_uuid


def test_collection_creation_and_state(in_memory_vector_store):
    """Verify that the collection is initialized with the proper vector configuration."""
    assert in_memory_vector_store.ensure_collection() is True
    assert in_memory_vector_store.count_chunks() == 0


def test_upsert_and_vector_search(in_memory_vector_store, sample_embedded_chunks):
    """Verify batch upsert and cosine similarity search ranking."""
    count = in_memory_vector_store.upsert_chunks(sample_embedded_chunks)
    assert count == 3
    assert in_memory_vector_store.count_chunks() == 3

    # Query using the exact vector of the first chunk (should rank #1 with score ~ 1.0)
    query_vector = sample_embedded_chunks[0].embedding
    results = in_memory_vector_store.search(query_vector=query_vector, top_k=2)

    assert len(results) == 2
    top = results[0]
    assert isinstance(top, ScoredChunk)
    assert top.retrieval_method == "vector"
    assert math.isclose(top.score, 1.0, rel_tol=1e-3)
    assert top.chunk.metadata.document_id == "doc_os"
    assert "Virtual memory" in top.chunk.content


def test_metadata_preservation(in_memory_vector_store, sample_embedded_chunks):
    """Verify all metadata fields and page numbers are preserved upon search retrieval."""
    in_memory_vector_store.upsert_chunks(sample_embedded_chunks)

    # Search for the database chunk
    query_vector = sample_embedded_chunks[2].embedding
    results = in_memory_vector_store.search(query_vector=query_vector, top_k=1)

    assert len(results) == 1
    meta = results[0].chunk.metadata
    assert meta.document_id == "doc_db"
    assert meta.document_name == "db_systems.pdf"
    assert meta.chunk_index == 0
    assert meta.page_number == 18
    assert meta.chunking_method == "recursive"
    assert meta.token_count_approx == 12


def test_document_deletion(in_memory_vector_store, sample_embedded_chunks):
    """Verify deleting a document by documentId removes its chunks and keeps others."""
    in_memory_vector_store.upsert_chunks(sample_embedded_chunks)
    assert in_memory_vector_store.count_chunks() == 3

    # Delete doc_os (2 chunks)
    success = in_memory_vector_store.delete_document("doc_os")
    assert success is True
    assert in_memory_vector_store.count_chunks() == 1

    # Search should now only return the remaining database chunk
    query_vector = sample_embedded_chunks[0].embedding
    results = in_memory_vector_store.search(query_vector=query_vector, top_k=5)
    assert len(results) == 1
    assert results[0].chunk.metadata.document_id == "doc_db"


def test_document_filter_search(in_memory_vector_store, sample_embedded_chunks):
    """Verify search filtering by documentId."""
    in_memory_vector_store.upsert_chunks(sample_embedded_chunks)

    # Search with a query vector but filter strictly for doc_db
    query_vector = sample_embedded_chunks[0].embedding  # Vector from doc_os
    results = in_memory_vector_store.search(
        query_vector=query_vector,
        top_k=5,
        filter_document_id="doc_db",
    )

    # Even though query vector is closest to doc_os, filter should only yield doc_db
    assert len(results) == 1
    assert results[0].chunk.metadata.document_id == "doc_db"


def test_empty_and_invalid_inputs(in_memory_vector_store):
    """Verify proper exception handling for invalid dimensions and parameters."""
    # Empty upsert
    assert in_memory_vector_store.upsert_chunks([]) == 0

    # Invalid vector dimension in search
    with pytest.raises(ValueError, match="query_vector dimension mismatch"):
        in_memory_vector_store.search(query_vector=[0.1, 0.2, 0.3])

    # Empty query vector
    with pytest.raises(ValueError, match="query_vector cannot be empty"):
        in_memory_vector_store.search(query_vector=[])

    # Invalid top_k
    with pytest.raises(ValueError, match="top_k must be positive"):
        in_memory_vector_store.search(query_vector=make_unit_vector(1), top_k=0)

    # Empty document_id on deletion
    with pytest.raises(ValueError, match="document_id cannot be empty"):
        in_memory_vector_store.delete_document("")

