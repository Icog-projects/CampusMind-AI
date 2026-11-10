"""
Tests for Grounded Answer Generation Service and LLM Service Layer.

Verifies:
1. Grounded prompt construction and untrusted data handling.
2. Direct inline citation mapping to Document Name, Page Number, and Chunk ID.
3. Filtering of unused source citations based on actual [N] references in answer text.
4. Handling empty retrieval without calling LLM.
5. Detection of insufficient evidence responses.
6. Missing API configuration error handling.
7. LLM API errors and timeouts handling.
8. Correct GroundedAnswer response schema structure.
"""

import pytest
from unittest.mock import MagicMock

from app.schemas.chunk import Chunk, ChunkMetadata, ScoredChunk, GroundedAnswer, SourceCitation
from app.services.llm_service import (
    BaseLLMProvider,
    GroqProvider,
    LLMConfigurationError,
    LLMTimeoutError,
    LLMAPIError,
)
from app.services.generation_service import GenerationService


def make_scored_chunk(doc_id: str, doc_name: str, chunk_id: str, page: int, content: str) -> ScoredChunk:
    chunk = Chunk(
        content=content,
        metadata=ChunkMetadata(
            documentId=doc_id,
            documentName=doc_name,
            chunkId=chunk_id,
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=page,
            tokenCountApprox=len(content.split()),
            characterCount=len(content),
        ),
    )
    return ScoredChunk(chunk=chunk, score=0.95, retrieval_method="hybrid")


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, response_text: str = "Test answer", model: str = "openai/gpt-oss-120b"):
        self.response_text = response_text
        self.model = model
        self.calls = []

    def generate(self, messages, temperature=0.1, max_tokens=1024, **kwargs):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        return {
            "content": self.response_text,
            "model": self.model,
            "prompt_tokens": 120,
            "completion_tokens": 45,
        }


def test_empty_retrieval_handles_without_llm():
    """Verify empty retrieval returns immediately without invoking LLM."""
    mock_provider = MockLLMProvider()
    service = GenerationService(llm_provider=mock_provider)

    result = service.generate_answer(question="What is the grading policy?", retrieved_chunks=[])

    assert isinstance(result, GroundedAnswer)
    assert not result.has_sufficient_context
    assert len(result.sources) == 0
    assert "No relevant documents" in result.answer
    assert len(mock_provider.calls) == 0  # LLM must not be called


def test_evidence_formatting_and_prompt_construction():
    """Verify retrieved chunks are formatted into numbered evidence entries."""
    c1 = make_scored_chunk("doc1", "Handbook.pdf", "chunk-01", 12, "Midterm exams are worth 30% of total grade.")
    c2 = make_scored_chunk("doc2", "Syllabus.docx", "chunk-02", 3, "Assignments must be submitted via the portal.")

    service = GenerationService(llm_provider=MockLLMProvider())
    evidence_block, citations = service.format_evidence([c1, c2])

    assert len(citations) == 2
    assert citations[0].citation_index == 1
    assert citations[0].document_name == "Handbook.pdf"
    assert citations[0].page_number == 12
    assert citations[0].chunk_id == "chunk-01"

    assert citations[1].citation_index == 2
    assert citations[1].document_name == "Syllabus.docx"
    assert citations[1].page_number == 3
    assert citations[1].chunk_id == "chunk-02"

    assert "[1] (Document: Handbook.pdf, Page 12, Chunk ID: chunk-01)" in evidence_block
    assert "[2] (Document: Syllabus.docx, Page 3, Chunk ID: chunk-02)" in evidence_block


def test_citation_generation_and_source_mapping():
    """Verify that only citations actually cited in the LLM answer are mapped and returned."""
    c1 = make_scored_chunk("doc1", "Handbook.pdf", "chunk-01", 12, "Midterm exams are worth 30% of total grade.")
    c2 = make_scored_chunk("doc2", "Syllabus.docx", "chunk-02", 3, "Assignments must be submitted via the portal.")

    # Model cites only [1]
    mock_provider = MockLLMProvider(
        response_text="The midterm examination accounts for 30% of the course grade [1]."
    )
    service = GenerationService(llm_provider=mock_provider)

    result = service.generate_answer(
        question="How much are midterms worth?",
        retrieved_chunks=[c1, c2],
    )

    assert isinstance(result, GroundedAnswer)
    assert result.has_sufficient_context is True
    assert result.model_name == "openai/gpt-oss-120b"
    assert "[1]" in result.answer

    # Since only [1] was cited, sources should only contain chunk-01
    assert len(result.sources) == 1
    assert result.sources[0].citation_index == 1
    assert result.sources[0].chunk_id == "chunk-01"
    assert result.sources[0].document_name == "Handbook.pdf"
    assert result.sources[0].page_number == 12


def test_insufficient_evidence_acknowledgment():
    """Verify service marks has_sufficient_context=False when LLM indicates insufficient information."""
    c1 = make_scored_chunk("doc1", "CampusMap.pdf", "chunk-01", 1, "The cafeteria is located in Building C.")

    mock_provider = MockLLMProvider(
        response_text="The provided documents do not contain sufficient information to answer when the library closes."
    )
    service = GenerationService(llm_provider=mock_provider)

    result = service.generate_answer(
        question="What time does the library close?",
        retrieved_chunks=[c1],
    )

    assert result.has_sufficient_context is False
    assert "not contain sufficient information" in result.answer.lower()


def test_missing_api_configuration():
    """Verify GroqProvider raises LLMConfigurationError if GROQ_API_KEY is missing or placeholder."""
    # When initialized with placeholder or empty key
    with pytest.raises(LLMConfigurationError) as exc_info:
        GroqProvider(api_key="your_groq_api_key_here")
    assert "GROQ_API_KEY is not configured" in str(exc_info.value)

    with pytest.raises(LLMConfigurationError):
        GroqProvider(api_key="")


def test_llm_api_failure_and_timeout_handling():
    """Verify provider maps timeout and API errors to domain exceptions."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("APITimeoutError: Connection timed out after 30s")

    provider = GroqProvider(api_key="gsk_valid_mock_key", client=mock_client)

    with pytest.raises(LLMTimeoutError) as exc_info:
        provider.generate(messages=[{"role": "user", "content": "Hello"}])
    assert "timed out" in str(exc_info.value).lower()

    # Generic API Error
    mock_client.chat.completions.create.side_effect = Exception("Rate limit reached for requests per minute")
    with pytest.raises(LLMAPIError) as exc_info:
        provider.generate(messages=[{"role": "user", "content": "Hello"}])
    assert "Rate limit" in str(exc_info.value)


def test_invalid_generation_arguments():
    """Verify validation on empty questions and invalid types."""
    service = GenerationService(llm_provider=MockLLMProvider())

    with pytest.raises(TypeError):
        service.generate_answer(question=123, retrieved_chunks=[])

    with pytest.raises(ValueError):
        service.generate_answer(question="   ", retrieved_chunks=[])

