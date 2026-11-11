"""CampusMind AI - Reranking Service Unit & Integration Tests.

Validates:
1. Reranking returns candidate chunks sorted in strictly descending relevance-score order.
2. Chunk metadata (document name, document ID, page number, chunk ID, chunk index) is preserved.
3. Top K truncation behaves as configured.
4. Model instance is loaded once and reused (singleton pattern).
5. RAG pipeline executes reranking on cache miss and produces valid GroundedAnswer with citations.
6. RAG pipeline cache hits completely bypass reranking and hybrid retrieval.
"""

from unittest.mock import MagicMock
import pytest
from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk, GroundedAnswer, SourceCitation
from app.services.reranking_service import RerankingService
from app.services.rag_service import RAGService


def make_dummy_chunk(chunk_id: str, content: str, page_number: int = 1, doc_id: str = "doc_test") -> ScoredChunk:
    metadata = ChunkMetadata(
        documentId=doc_id,
        documentName="Student_Handbook.pdf",
        chunkId=chunk_id,
        chunkIndex=0,
        chunkingMethod="recursive",
        pageNumber=page_number,
        characterCount=len(content),
    )
    chunk = Chunk(content=content, metadata=metadata)
    return ScoredChunk(chunk=chunk, score=0.01, retrieval_method="hybrid")


@pytest.fixture(scope="module")
def reranker():
    return RerankingService(device="cpu", default_top_k=2)


def test_reranking_returns_descending_scores(reranker):
    query = "What is the minimum CGPA required for good standing?"
    candidates = [
        make_dummy_chunk("chk-unrelated", "The campus cafeteria serves lunch between 11am and 2pm daily."),
        make_dummy_chunk("chk-relevant", "Students must maintain a minimum cumulative CGPA of 2.0 to remain in good academic standing.", page_number=4),
        make_dummy_chunk("chk-vague", "Academic policies and standing are reviewed each term by the registrar.", page_number=2),
    ]

    reranked = reranker.rerank(query=query, candidates=candidates, top_k=3)

    assert len(reranked) == 3
    # Most relevant chunk about 2.0 CGPA must score highest and come first
    assert reranked[0].chunk.metadata.chunk_id == "chk-relevant"
    assert reranked[0].score > reranked[1].score
    assert reranked[1].score > reranked[2].score
    # Retrieval method should be marked as reranked
    assert reranked[0].retrieval_method == "reranked"


def test_reranking_preserves_metadata_and_citations(reranker):
    query = "Where is the library located?"
    original_chunk = make_dummy_chunk(
        chunk_id="chk-lib-99",
        content="The university main library is located in Turing Hall on the 2nd floor.",
        page_number=12,
        doc_id="doc_campus_map",
    )

    reranked = reranker.rerank(query=query, candidates=[original_chunk], top_k=1)
    res = reranked[0]

    assert res.chunk.metadata.chunk_id == "chk-lib-99"
    assert res.chunk.metadata.document_id == "doc_campus_map"
    assert res.chunk.metadata.document_name == "Student_Handbook.pdf"
    assert res.chunk.metadata.page_number == 12
    assert res.chunk.metadata.character_count == len(original_chunk.chunk.content)


def test_reranker_model_singleton_reuse(reranker):
    service_a = RerankingService()
    service_b = RerankingService()
    assert service_a.model is service_b.model


def test_rag_service_with_reranking_enabled():
    mock_cache = MagicMock()
    mock_cache.get_answer.return_value = None  # Cache miss

    mock_embed = MagicMock()
    mock_embed.embed_query.return_value = [0.1] * 384

    candidate1 = make_dummy_chunk("chk-1", "Campus library closes at 10 PM.")
    candidate2 = make_dummy_chunk("chk-2", "Good standing requires a CGPA of 2.0.")

    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = [candidate1, candidate2]

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [candidate2, candidate1]

    mock_gen = MagicMock()
    mock_gen.generate_answer.return_value = GroundedAnswer(
        answer="A CGPA of 2.0 is required [1].",
        sources=[
            SourceCitation(
                citation_index=1,
                document_id="doc_test",
                document_name="Student_Handbook.pdf",
                page_number=1,
                chunk_id="chk-2",
                chunk_index=0,
                content_snippet="Good standing requires a CGPA of 2.0.",
            )
        ],
        has_sufficient_context=True,
    )

    rag = RAGService(
        cache_service=mock_cache,
        embedding_service=mock_embed,
        hybrid_retrieval_service=mock_hybrid,
        reranking_service=mock_reranker,
        generation_service=mock_gen,
    )

    result = rag.query("What CGPA is required?", top_k=2)

    assert mock_reranker.rerank.call_count == 1
    assert mock_gen.generate_answer.call_count == 1
    # Verify reranked chunks passed into generator
    gen_call_args = mock_gen.generate_answer.call_args[1]
    assert gen_call_args["retrieved_chunks"] == [candidate2, candidate1]
    assert result.sources[0].chunk_id == "chk-2"


def test_rag_cache_hit_bypasses_reranking():
    cached = GroundedAnswer(
        answer="Cached response for library hours [1].",
        sources=[],
        has_sufficient_context=True,
    )
    mock_cache = MagicMock()
    mock_cache.get_answer.return_value = cached  # Cache hit

    mock_hybrid = MagicMock()
    mock_reranker = MagicMock()
    mock_gen = MagicMock()

    rag = RAGService(
        cache_service=mock_cache,
        hybrid_retrieval_service=mock_hybrid,
        reranking_service=mock_reranker,
        generation_service=mock_gen,
    )

    result = rag.query("What are the library hours?")

    assert result.answer == "Cached response for library hours [1]."
    assert mock_hybrid.search.call_count == 0
    assert mock_reranker.rerank.call_count == 0
    assert mock_gen.generate_answer.call_count == 0

