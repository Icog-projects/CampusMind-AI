"""
Focused tests for the Embedding Service in CampusMind AI.
Tests verify:
- Single text embedding generation.
- Multiple chunk embedding generation with 1-to-1 association.
- Exact 384-dimensional vector size.
- Normalized vector properties (unit L2 norm ~ 1.0).
- Batch processing with configurable batch size.
- Full metadata preservation across embedded chunks.
- Graceful handling of empty input and invalid types.
- Query embedding behavior.
- Sequence length validation against the 512-token limit.
- Reusing the loaded model instance.
"""

import math
import pytest
from app.services.embedding_service import (
    EmbeddingService,
    InputSequenceTooLongError,
    EXPECTED_DIMENSION,
    MAX_SEQUENCE_LENGTH,
)
from app.schemas.chunk import Chunk, ChunkMetadata


@pytest.fixture(scope="module")
def embedding_service():
    """Initializes a shared EmbeddingService fixture to reuse the loaded model."""
    return EmbeddingService(batch_size=8)


def test_model_loaded_once():
    """Verify that multiple EmbeddingService instances share the same loaded model."""
    service_a = EmbeddingService()
    service_b = EmbeddingService()
    assert service_a.model is service_b.model, "Model must be loaded once and reused across instances"
    assert service_a.tokenizer is not None


def test_single_text_embedding(embedding_service):
    """Verify embedding a single string yields a normalized 384-dim vector."""
    text = "CampusMind AI provides intelligent study assistance."
    vector = embedding_service.embed_text(text)

    # Dimension check
    assert isinstance(vector, list)
    assert len(vector) == EXPECTED_DIMENSION, f"Expected 384 dimensions, got {len(vector)}"

    # Normalization check: L2 norm of normalized vector should equal 1.0 (within float precision)
    norm = math.sqrt(sum(x * x for x in vector))
    assert math.isclose(norm, 1.0, rel_tol=1e-4), f"Vector is not normalized, norm={norm}"


def test_query_embedding(embedding_service):
    """Verify embedding a user query yields a 384-dim normalized vector."""
    query = "What are the requirements for operating systems?"
    vector = embedding_service.embed_query(query)

    assert isinstance(vector, list)
    assert len(vector) == EXPECTED_DIMENSION
    norm = math.sqrt(sum(x * x for x in vector))
    assert math.isclose(norm, 1.0, rel_tol=1e-4)


def test_multiple_chunk_embeddings_and_metadata_preservation(embedding_service):
    """Verify batch processing preserves 1-to-1 association and all metadata."""
    chunks = [
        Chunk(
            content="Process management handles execution state.",
            metadata=ChunkMetadata(
                documentId="doc_os_1",
                documentName="os.pdf",
                chunkId="chunk-001",
                chunkIndex=0,
                chunkingMethod="recursive",
                pageNumber=1,
                characterCount=43,
                tokenCountApprox=6,
            ),
        ),
        Chunk(
            content="Memory management tracks primary memory allocation.",
            metadata=ChunkMetadata(
                documentId="doc_os_1",
                documentName="os.pdf",
                chunkId="chunk-002",
                chunkIndex=1,
                chunkingMethod="recursive",
                pageNumber=2,
                characterCount=51,
                tokenCountApprox=7,
            ),
        ),
        Chunk(
            content="Virtual memory allows executing partially-loaded processes.",
            metadata=ChunkMetadata(
                documentId="doc_os_1",
                documentName="os.pdf",
                chunkId="chunk-003",
                chunkIndex=2,
                chunkingMethod="recursive",
                pageNumber=3,
                characterCount=59,
                tokenCountApprox=8,
            ),
        ),
    ]

    embedded_chunks = embedding_service.embed_chunks(chunks, batch_size=2)

    assert len(embedded_chunks) == 3

    # Check that each chunk is mapped correctly and retains metadata
    for i, ec in enumerate(embedded_chunks):
        assert ec.chunk.metadata.chunk_id == chunks[i].metadata.chunk_id
        assert ec.chunk.metadata.document_id == "doc_os_1"
        assert ec.chunk.metadata.document_name == "os.pdf"
        assert ec.chunk.metadata.chunk_index == i
        assert ec.chunk.metadata.page_number == i + 1
        assert ec.chunk.metadata.chunking_method == "recursive"
        assert len(ec.embedding) == 384
        # Verify L2 norm is ~1.0
        norm = math.sqrt(sum(x * x for x in ec.embedding))
        assert math.isclose(norm, 1.0, rel_tol=1e-4)


def test_empty_and_invalid_inputs(embedding_service):
    """Verify robust handling of empty text, empty chunk lists, and invalid input types."""
    # Empty string text
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        embedding_service.embed_text("")

    with pytest.raises(ValueError, match="empty or whitespace-only"):
        embedding_service.embed_text("   \n\t ")

    # Empty query
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        embedding_service.embed_query("")

    # Invalid types
    with pytest.raises(TypeError):
        embedding_service.embed_text(12345)

    with pytest.raises(TypeError):
        embedding_service.embed_query(None)

    # Empty chunks list should return empty list gracefully
    assert embedding_service.embed_chunks([]) == []

    # Invalid chunk item
    with pytest.raises(TypeError):
        embedding_service.embed_chunks(["not a chunk object"])

    # Chunk with empty text
    empty_content_chunk = Chunk(
        content="   ",
        metadata=ChunkMetadata(
            documentId="doc_err",
            documentName="err.txt",
            chunkId="err_1",
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=1,
            characterCount=0,
        ),
    )
    with pytest.raises(ValueError, match="contains empty text"):
        embedding_service.embed_chunks([empty_content_chunk])


def test_sequence_length_limit_detection(embedding_service):
    """Verify that inputs exceeding 512 tokens trigger InputSequenceTooLongError explicitly."""
    # Generate an oversized text (~700 tokens)
    oversized_text = "word " * 750
    token_count = embedding_service.count_tokens(oversized_text)
    assert token_count > MAX_SEQUENCE_LENGTH, f"Generated text only had {token_count} tokens"

    # Must raise InputSequenceTooLongError rather than silently truncating
    with pytest.raises(InputSequenceTooLongError, match="exceeds the model limit"):
        embedding_service.embed_text(oversized_text)

    with pytest.raises(InputSequenceTooLongError, match="exceeds the model limit"):
        embedding_service.embed_query(oversized_text)

    # Verify chunk-level detection
    oversized_chunk = Chunk(
        content=oversized_text,
        metadata=ChunkMetadata(
            documentId="doc_long",
            documentName="long.txt",
            chunkId="long_1",
            chunkIndex=0,
            chunkingMethod="recursive",
            pageNumber=1,
            characterCount=len(oversized_text),
        ),
    )
    with pytest.raises(InputSequenceTooLongError, match="exceeds the model limit"):
        embedding_service.embed_chunks([oversized_chunk])

