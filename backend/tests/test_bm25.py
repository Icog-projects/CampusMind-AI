"""
Unit tests for the BM25 Keyword Retrieval Service in CampusMind AI.
Verifies:
- Index creation from Chunk objects.
- Keyword-based retrieval and relevance scoring.
- Correct ranking of relevant chunks across distinct lecture topics.
- Configurable top_k parameter enforcement.
- Complete metadata and page-number preservation.
- Handling of empty collections, empty queries, invalid top_k, and duplicates.
- Dynamic index rebuilding when documents are added or removed.
"""

import pytest
from app.services.retrieval_bm25 import BM25RetrievalService, default_tokenizer
from app.schemas.chunk import Chunk, ChunkMetadata


# Multi-topic test corpus chunks (Operating Systems, Database Systems, Computer Networks)
@pytest.fixture
def sample_lecture_chunks():
    return [
        # OS Topic
        Chunk(
            content="Virtual memory allows execution of processes that are not completely in main memory.",
            metadata=ChunkMetadata(
                documentId="doc_os",
                documentName="os_lecture_3.pdf",
                chunkId="chunk_os_01",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=12,
                characterCount=83,
                tokenCountApprox=14,
            ),
        ),
        Chunk(
            content="Process scheduling algorithms include round-robin, priority scheduling, and shortest job first.",
            metadata=ChunkMetadata(
                documentId="doc_os",
                documentName="os_lecture_3.pdf",
                chunkId="chunk_os_02",
                chunkIndex=1,
                chunkingMethod="recursive",
                pageNumber=15,
                characterCount=96,
                tokenCountApprox=14,
            ),
        ),
        # Database Topic
        Chunk(
            content="Relational databases use B-tree and B+ tree indexing structures to accelerate SQL query execution.",
            metadata=ChunkMetadata(
                documentId="doc_db",
                documentName="db_systems.pdf",
                chunkId="chunk_db_01",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=4,
                characterCount=98,
                tokenCountApprox=14,
            ),
        ),
        Chunk(
            content="ACID properties ensure database transaction reliability: atomicity, consistency, isolation, and durability.",
            metadata=ChunkMetadata(
                documentId="doc_db",
                documentName="db_systems.pdf",
                chunkId="chunk_db_02",
                chunkIndex=1,
                chunkingMethod="recursive",
                pageNumber=7,
                characterCount=108,
                tokenCountApprox=14,
            ),
        ),
        # Networks Topic
        Chunk(
            content="The TCP three-way handshake establishes a reliable connection using SYN, SYN-ACK, and ACK packets.",
            metadata=ChunkMetadata(
                documentId="doc_net",
                documentName="networks_intro.pdf",
                chunkId="chunk_net_01",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=22,
                characterCount=100,
                tokenCountApprox=15,
            ),
        ),
    ]


@pytest.fixture
def bm25_service(sample_lecture_chunks):
    service = BM25RetrievalService()
    service.build_index(sample_lecture_chunks)
    return service


def test_tokenizer():
    """Verify standard tokenizer extracts lowercased alphanumeric words."""
    tokens = default_tokenizer("Hello, World! This is BM25-based search.")
    assert tokens == ["hello", "world", "this", "is", "bm25", "based", "search"]
    assert default_tokenizer("") == []
    assert default_tokenizer("   !@#$%^   ") == []


def test_index_creation_and_state(bm25_service, sample_lecture_chunks):
    """Verify index is created properly and reports correct size."""
    assert bm25_service.is_indexed is True
    assert bm25_service.total_chunks == len(sample_lecture_chunks)


def test_keyword_retrieval_and_ranking(bm25_service):
    """Verify relevant chunks are found and ranked at the top based on keywords."""
    # Query specific to Database indexing
    results = bm25_service.search("B-tree SQL indexing", top_k=3)
    assert len(results) > 0

    top_result = results[0]
    assert top_result.chunk.metadata.document_id == "doc_db"
    assert "B-tree" in top_result.chunk.content
    assert top_result.score > 0.0
    assert top_result.retrieval_method == "bm25"

    # Query specific to Networking
    net_results = bm25_service.search("TCP handshake SYN packet", top_k=2)
    assert len(net_results) > 0
    assert net_results[0].chunk.metadata.document_id == "doc_net"
    assert "three-way handshake" in net_results[0].chunk.content


def test_metadata_preservation(bm25_service):
    """Verify full metadata and page numbers are preserved on returned ScoredChunks."""
    results = bm25_service.search("virtual memory", top_k=1)
    assert len(results) == 1

    scored_chunk = results[0]
    meta = scored_chunk.chunk.metadata
    assert meta.document_id == "doc_os"
    assert meta.document_name == "os_lecture_3.pdf"
    assert meta.chunk_id == "chunk_os_01"
    assert meta.page_number == 12
    assert meta.chunking_method == "recursive"


def test_configurable_top_k(bm25_service):
    """Verify that top_k strictly limits the number of results returned."""
    # Query with terms appearing across multiple chunks
    results_k1 = bm25_service.search("memory process database", top_k=1)
    assert len(results_k1) == 1

    results_k2 = bm25_service.search("memory process database", top_k=2)
    assert len(results_k2) == 2

    results_k5 = bm25_service.search("memory process database", top_k=5)
    assert len(results_k5) <= 5


def test_empty_and_invalid_inputs(bm25_service):
    """Verify handling of empty queries, empty index, and invalid parameters."""
    # Empty or whitespace query
    assert bm25_service.search("") == []
    assert bm25_service.search("   \n\t  ") == []

    # Non-string query
    with pytest.raises(TypeError):
        bm25_service.search(None)

    # Invalid top_k
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        bm25_service.search("process", top_k=0)

    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        bm25_service.search("process", top_k=-2)

    # Search on empty index
    empty_service = BM25RetrievalService()
    assert empty_service.is_indexed is False
    assert empty_service.search("process") == []


def test_deduplication_on_index_build():
    """Verify that duplicate chunks are safely deduplicated."""
    chunk = Chunk(
        content="Unique chunk text.",
        metadata=ChunkMetadata(
            documentId="doc_dupe",
            documentName="test.pdf",
            chunkId="dupe_id_01",
            chunkIndex=0,
            chunkingMethod="recursive",
            characterCount=18,
        ),
    )
    service = BM25RetrievalService()
    count = service.build_index([chunk, chunk, chunk], deduplicate=True)
    assert count == 1
    assert service.total_chunks == 1


def test_index_rebuilding(sample_lecture_chunks):
    """Verify dynamic index rebuilding when adding and removing documents."""
    service = BM25RetrievalService()
    service.build_index(sample_lecture_chunks)
    assert service.total_chunks == 5

    # Remove the Operating Systems document
    remaining = service.remove_document("doc_os")
    assert remaining == 3
    assert service.total_chunks == 3

    # OS queries should now return zero results
    os_results = service.search("virtual memory processes")
    assert len(os_results) == 0

    # Add a new document chunk
    new_chunk = Chunk(
        content="Compilers translate high-level code into target assembly language.",
        metadata=ChunkMetadata(
            documentId="doc_compiler",
            documentName="compilers_101.pdf",
            chunkId="chunk_comp_01",
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=1,
            characterCount=66,
        ),
    )
    service.add_chunks([new_chunk])
    assert service.total_chunks == 4

    # Search for newly added compiler content
    comp_results = service.search("compiler assembly language", top_k=1)
    assert len(comp_results) == 1
    assert comp_results[0].chunk.metadata.document_id == "doc_compiler"

