"""
Tests for CampusMind AI - Hybrid Retrieval Service (Reciprocal Rank Fusion - RRF).

Verifies:
1. compute_rrf mathematical accuracy: 1 / (k + rank).
2. Proper fusion of results from both BM25 and vector search.
3. De-duplication and score summation when a chunk is present in both rankings.
4. Retention of chunks present in only one search method.
5. Strict adherence to configurable top_k and candidate_limit.
6. Full preservation of chunk content and ChunkMetadata.
7. Document-level filtering (filter_document_id) across both search methods.
8. Graceful handling of empty inputs, missing components, and invalid parameters.
"""

import pytest
from app.schemas.chunk import Chunk, ChunkMetadata, EmbeddedChunk, ScoredChunk
from app.services.retrieval_bm25 import BM25RetrievalService
from app.services.vector_store import VectorStoreService
from app.services.hybrid_retrieval import HybridRetrievalService, compute_rrf, DEFAULT_RRF_K


def make_chunk(doc_id: str, doc_name: str, chunk_id: str, index: int, content: str) -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            documentId=doc_id,
            documentName=doc_name,
            chunkId=chunk_id,
            chunkIndex=index,
            chunkingMethod="recursive",
            pageNumber=1,
            tokenCountApprox=10,
            characterCount=len(content),
        ),
    )


def test_rrf_formula_calculation():
    """Verify that RRF score calculation exactly adheres to 1 / (k + rank)."""
    c1 = make_chunk("doc1", "doc1.txt", "chunk-1", 0, "First chunk")
    c2 = make_chunk("doc1", "doc1.txt", "chunk-2", 1, "Second chunk")
    c3 = make_chunk("doc1", "doc1.txt", "chunk-3", 2, "Third chunk")

    # List 1: c1 (rank 1), c2 (rank 2)
    list1 = [
        ScoredChunk(chunk=c1, score=10.0, retrieval_method="bm25"),
        ScoredChunk(chunk=c2, score=5.0, retrieval_method="bm25"),
    ]
    # List 2: c2 (rank 1), c3 (rank 2)
    list2 = [
        ScoredChunk(chunk=c2, score=0.9, retrieval_method="vector"),
        ScoredChunk(chunk=c3, score=0.8, retrieval_method="vector"),
    ]

    k = 60
    # Expected scores:
    # c2 appears in list1 at rank 2: 1/(60+2) = 1/62
    # c2 appears in list2 at rank 1: 1/(60+1) = 1/61
    # expected c2 score = (1/61) + (1/62) ~ 0.0163934 + 0.0161290 = 0.0325224
    expected_c2_score = (1.0 / 61.0) + (1.0 / 62.0)

    # c1 appears in list1 at rank 1: 1/(60+1) = 1/61
    expected_c1_score = 1.0 / 61.0

    # c3 appears in list2 at rank 2: 1/(60+2) = 1/62
    expected_c3_score = 1.0 / 62.0

    fused = compute_rrf([list1, list2], k=k, top_k=5)

    assert len(fused) == 3
    # c2 must rank 1st because it appeared in both
    assert fused[0].chunk.metadata.chunk_id == "chunk-2"
    assert pytest.approx(fused[0].score, rel=1e-5) == expected_c2_score
    assert fused[0].retrieval_method == "hybrid"

    # c1 ranks 2nd
    assert fused[1].chunk.metadata.chunk_id == "chunk-1"
    assert pytest.approx(fused[1].score, rel=1e-5) == expected_c1_score
    assert fused[1].retrieval_method == "hybrid"

    # c3 ranks 3rd
    assert fused[2].chunk.metadata.chunk_id == "chunk-3"
    assert pytest.approx(fused[2].score, rel=1e-5) == expected_c3_score
    assert fused[2].retrieval_method == "hybrid"


def test_retention_of_single_method_chunks():
    """Verify that chunks present in only BM25 or only vector retrieval are retained."""
    c_bm25 = make_chunk("doc1", "doc1.txt", "chunk-bm25", 0, "BM25 unique chunk")
    c_vector = make_chunk("doc2", "doc2.txt", "chunk-vector", 0, "Vector unique chunk")

    list_bm25 = [ScoredChunk(chunk=c_bm25, score=8.0, retrieval_method="bm25")]
    list_vector = [ScoredChunk(chunk=c_vector, score=0.85, retrieval_method="vector")]

    fused = compute_rrf([list_bm25, list_vector], k=60, top_k=10)

    assert len(fused) == 2
    ids = {item.chunk.metadata.chunk_id for item in fused}
    assert "chunk-bm25" in ids
    assert "chunk-vector" in ids
    for item in fused:
        assert item.retrieval_method == "hybrid"


def test_top_k_limiting():
    """Verify that top_k restricts the number of returned chunks."""
    chunks = [
        make_chunk("doc1", "doc1.txt", f"c-{i}", i, f"Content {i}")
        for i in range(10)
    ]
    ranked_list = [
        ScoredChunk(chunk=c, score=10.0 - i, retrieval_method="bm25")
        for i, c in enumerate(chunks)
    ]

    fused = compute_rrf([ranked_list], k=60, top_k=3)
    assert len(fused) == 3
    assert fused[0].chunk.metadata.chunk_id == "c-0"
    assert fused[1].chunk.metadata.chunk_id == "c-1"
    assert fused[2].chunk.metadata.chunk_id == "c-2"


def test_metadata_preservation():
    """Ensure all original ChunkMetadata fields and text content remain untouched."""
    original = make_chunk("doc_meta", "Handbook.pdf", "chunk-xyz", 7, "Important handbook rule")
    scored = ScoredChunk(chunk=original, score=5.5, retrieval_method="bm25")

    fused = compute_rrf([[scored]], k=60, top_k=1)
    assert len(fused) == 1
    res = fused[0]

    assert res.chunk.content == "Important handbook rule"
    assert res.chunk.metadata.document_id == "doc_meta"
    assert res.chunk.metadata.document_name == "Handbook.pdf"
    assert res.chunk.metadata.chunk_id == "chunk-xyz"
    assert res.chunk.metadata.chunk_index == 7
    assert res.chunk.metadata.chunking_method == "recursive"
    assert res.chunk.metadata.page_number == 1
    assert res.chunk.metadata.character_count == len("Important handbook rule")
    assert res.retrieval_method == "hybrid"


def test_hybrid_service_integration():
    """Test full integration of HybridRetrievalService using BM25 and in-memory VectorStore."""
    # Build BM25 index
    bm25_service = BM25RetrievalService()
    c1 = make_chunk("docA", "docA.txt", "chunk-A1", 0, "Machine learning algorithms and deep neural networks.")
    c2 = make_chunk("docA", "docA.txt", "chunk-A2", 1, "Database systems relational algebra and SQL indexing.")
    c3 = make_chunk("docB", "docB.txt", "chunk-B1", 0, "Campus life student clubs sports and library timings.")
    bm25_service.build_index([c1, c2, c3])

    # Build Vector Store
    vector_store = VectorStoreService()
    # Create mock orthogonal 384-d vectors
    v1 = [0.0] * 384
    v1[0] = 1.0  # matches query_vector along dim 0

    v2 = [0.0] * 384
    v2[1] = 1.0  # orthogonal

    v3 = [0.0] * 384
    v3[2] = 1.0  # orthogonal

    emb1 = EmbeddedChunk(chunk=c1, embedding=v1)
    emb2 = EmbeddedChunk(chunk=c2, embedding=v2)
    emb3 = EmbeddedChunk(chunk=c3, embedding=v3)
    vector_store.upsert_chunks([emb1, emb2, emb3])

    hybrid_service = HybridRetrievalService(bm25_service=bm25_service, vector_store=vector_store)

    # Query matching c1 both lexically ("machine learning") and semantically (v1 along dim 0)
    query_text = "machine learning"
    query_vec = [0.0] * 384
    query_vec[0] = 1.0

    results = hybrid_service.search(query=query_text, query_vector=query_vec, top_k=2)

    assert len(results) <= 2
    assert len(results) >= 1
    # chunk-A1 must be rank #1 because it matches both BM25 and Vector search
    assert results[0].chunk.metadata.chunk_id == "chunk-A1"
    assert results[0].retrieval_method == "hybrid"


def test_hybrid_service_document_filtering():
    """Test that filter_document_id filters results across both BM25 and VectorStore."""
    bm25_service = BM25RetrievalService()
    c1 = make_chunk("docA", "docA.txt", "chunk-A1", 0, "Physics laboratory safety procedures.")
    c2 = make_chunk("docB", "docB.txt", "chunk-B1", 0, "Physics lecture schedule and room assignment.")
    bm25_service.build_index([c1, c2])

    vector_store = VectorStoreService()
    v1 = [1.0] + [0.0] * 383
    v2 = [1.0] + [0.0] * 383
    vector_store.upsert_chunks([
        EmbeddedChunk(chunk=c1, embedding=v1),
        EmbeddedChunk(chunk=c2, embedding=v2),
    ])

    hybrid_service = HybridRetrievalService(bm25_service=bm25_service, vector_store=vector_store)

    query_vec = [1.0] + [0.0] * 383
    results = hybrid_service.search(
        query="Physics",
        query_vector=query_vec,
        filter_document_id="docB",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk.metadata.document_id == "docB"
    assert results[0].chunk.metadata.chunk_id == "chunk-B1"


def test_empty_and_invalid_inputs():
    """Test edge cases: empty queries, None services, invalid top_k, invalid k."""
    hybrid_service = HybridRetrievalService(bm25_service=None, vector_store=None)

    # Both services None -> empty list
    empty_res = hybrid_service.search(query="anything", top_k=5)
    assert empty_res == []

    # Invalid top_k
    with pytest.raises(ValueError):
        hybrid_service.search(query="test", top_k=0)

    # Invalid k
    with pytest.raises(ValueError):
        hybrid_service.search(query="test", top_k=5, k=-1)

    # Invalid query type
    with pytest.raises(TypeError):
        hybrid_service.search(query=123, top_k=5)

    # Empty query string and no query_vector
    assert hybrid_service.search(query="   ") == []

    # compute_rrf empty inputs
    assert compute_rrf([]) == []
    assert compute_rrf([[]]) == []

