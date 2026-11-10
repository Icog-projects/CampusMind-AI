"""
Unit tests for Chunking Service in CampusMind AI.
Verifies all three chunking methods:
1. Recursive Character Chunking.
2. Fixed-Size Chunking.
3. Genuine Semantic Chunking.

Tests cover:
- Configurable chunk size and overlap across methods.
- Document and page provenance metadata preservation.
- Sentence boundary detection and cosine similarity topic splitting in semantic chunking.
- Unified chunk_document dispatcher.
- Handling empty, short, and invalid inputs.
- No unintended text loss.
"""

import pytest
from unittest.mock import MagicMock

from app.services.chunking_service import (
    ChunkingService,
    approximate_tokens_from_words,
    split_into_sentences,
    cosine_similarity,
)
from app.schemas.chunk import ExtractedDocument, ExtractedPage


SAMPLE_COURSE_TEXT = """Introduction to Operating Systems.
An operating system is system software that manages computer hardware and software resources.
Time-sharing operating systems schedule tasks for efficient use of the system.

Process Management and Lifecycle.
A process is a program in execution progressing sequentially.
A process includes code, program counter, and registers.

Memory Management and Virtual Memory.
Memory management oversees primary memory and moves processes back and forth.
It tracks each and every memory location whether allocated or free.
"""


@pytest.fixture
def chunking_service():
    return ChunkingService(default_chunk_size_tokens=500, default_chunk_overlap_tokens=75)


def test_token_sizing_distinction():
    """Verify that token metrics are distinct from character counts."""
    text = "The quick brown fox jumps over the lazy dog."
    chars = len(text)
    tokens = approximate_tokens_from_words(text)
    assert chars == 44
    assert tokens == int(9 * 1.33)  # 11 tokens
    assert chars != tokens, "Character count must not be conflated with token count"


def test_invalid_configurations(chunking_service):
    """Verify ValueError is raised on non-positive chunk size or overlap >= chunk size."""
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        chunking_service.recursive_chunking("Sample text", chunk_size_tokens=0)

    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        chunking_service.fixed_chunking("Sample text", chunk_size_tokens=100, chunk_overlap_tokens=-5)

    with pytest.raises(ValueError, match="strictly smaller than chunk_size"):
        chunking_service.semantic_chunking("Sample text", chunk_size_tokens=100, chunk_overlap_tokens=100)


def test_empty_and_short_input_handling(chunking_service):
    """Verify empty text or whitespace returns empty lists cleanly across all methods."""
    assert chunking_service.recursive_chunking("") == []
    assert chunking_service.fixed_chunking("   ") == []
    assert chunking_service.semantic_chunking("") == []
    assert chunking_service.chunk_document("", method="recursive") == []
    assert chunking_service.chunk_document("", method="fixed") == []
    assert chunking_service.chunk_document("", method="semantic") == []

    # Very short single-sentence text
    short_text = "Single short sentence."
    chunks_fixed = chunking_service.fixed_chunking(short_text)
    chunks_rec = chunking_service.recursive_chunking(short_text)
    chunks_sem = chunking_service.semantic_chunking(short_text)

    assert len(chunks_fixed) == 1
    assert len(chunks_rec) == 1
    assert len(chunks_sem) == 1
    assert chunks_sem[0].content == short_text
    assert chunks_sem[0].metadata.chunking_method == "semantic"


# -----------------------------------------------------------------------------
# Fixed-Size Chunking Tests
# -----------------------------------------------------------------------------
def test_fixed_size_chunking_window_and_overlap(chunking_service):
    """Verify fixed-size chunking splits text with sliding window and overlap."""
    text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
    # Target 8 tokens (~6 words per chunk) with 2 tokens (~1 word overlap)
    chunks = chunking_service.fixed_chunking(
        text,
        document_id="doc-fixed",
        document_name="FixedDoc.txt",
        chunk_size_tokens=8,
        chunk_overlap_tokens=2,
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata.chunking_method == "fixed"
        assert chunk.metadata.document_id == "doc-fixed"
        assert chunk.metadata.document_name == "FixedDoc.txt"
        assert chunk.metadata.character_count == len(chunk.content)

    # First chunk should start with word1
    assert chunks[0].content.startswith("word1")
    # All words must be represented across chunks
    all_combined = " ".join(c.content for c in chunks)
    for word in text.split():
        assert word in all_combined


# -----------------------------------------------------------------------------
# Semantic Chunking Tests
# -----------------------------------------------------------------------------
def test_split_into_sentences():
    """Verify accurate sentence tokenization."""
    text = "First sentence here. Second sentence starts! Is this the third? Yes, it is."
    sents = split_into_sentences(text)
    assert len(sents) == 4
    assert sents[0] == "First sentence here."
    assert sents[1] == "Second sentence starts!"
    assert sents[2] == "Is this the third?"
    assert sents[3] == "Yes, it is."


def test_semantic_chunking_with_mock_embedding():
    """
    Verify genuine semantic boundary detection:
    Sentence 1 and 2 share high similarity (same topic).
    Sentence 3 is completely different (low similarity -> topic boundary).
    """
    mock_embedder = MagicMock()

    # Define mock sentence vectors:
    # s1 & s2 align on dim 0 (similarity 1.0)
    # s3 aligns on dim 1 (similarity 0.0 with s2 -> triggers semantic split)
    v_topic_a = [1.0, 0.0, 0.0]
    v_topic_b = [0.0, 1.0, 0.0]

    def mock_embed(text: str):
        if "operating system" in text.lower() or "hardware" in text.lower():
            return v_topic_a
        return v_topic_b

    mock_embedder.embed_text.side_effect = mock_embed

    service = ChunkingService(
        embedding_service=mock_embedder,
        default_chunk_size_tokens=500,
        default_chunk_overlap_tokens=0,
        default_similarity_threshold=0.6,
    )

    doc_text = (
        "Operating systems manage computer hardware resources. "
        "They schedule tasks for efficient CPU utilization. "
        "Cooking pasta requires boiling water and adding salt."
    )

    chunks = service.semantic_chunking(
        doc_text,
        document_id="doc_sem",
        document_name="Lecture.txt",
        similarity_threshold=0.6,
        chunk_overlap_tokens=0,
    )

    # Should detect boundary before cooking pasta
    assert len(chunks) == 2
    assert "Operating systems" in chunks[0].content
    assert "Cooking pasta" in chunks[1].content
    assert chunks[0].metadata.chunking_method == "semantic"
    assert chunks[1].metadata.chunking_method == "semantic"


# -----------------------------------------------------------------------------
# Unified Interface & Metadata Preservation Tests
# -----------------------------------------------------------------------------
def test_unified_dispatcher_and_metadata_preservation(chunking_service):
    """Verify chunk_document dispatches to all three methods correctly."""
    doc = ExtractedDocument(
        document_id="doc-multi",
        document_name="Syllabus.pdf",
        pages=[
            ExtractedPage(page_number=1, text="Page one course objectives and grading."),
            ExtractedPage(page_number=2, text="Page two required textbooks and lab schedule."),
        ],
    )

    for method in ["recursive", "fixed", "semantic"]:
        chunks = chunking_service.chunk_document(doc, method=method, chunk_size_tokens=100, chunk_overlap_tokens=10)
        assert len(chunks) >= 2
        for idx, chunk in enumerate(chunks):
            assert chunk.metadata.document_id == "doc-multi"
            assert chunk.metadata.document_name == "Syllabus.pdf"
            assert chunk.metadata.chunking_method == method
            assert chunk.metadata.chunk_index == idx
            assert chunk.metadata.page_number in [1, 2]
            assert chunk.metadata.token_count_approx is not None
            assert chunk.metadata.character_count == len(chunk.content)

    # Invalid method check
    with pytest.raises(ValueError, match="Unknown chunking method"):
        chunking_service.chunk_document(doc, method="invalid_method")
