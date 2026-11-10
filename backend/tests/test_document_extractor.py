"""
Unit tests for CampusMind AI Document Extractor Service (FR-01, FR-02).

Verifies:
1. PDF extraction using PyMuPDF with accurate 1-based page numbers.
2. DOCX extraction with paragraphs and explicit page breaks.
3. TXT extraction with single-page representation and encoding support.
4. Validation of supported extensions (.pdf, .docx, .txt) and rejection of unsupported types (.exe, .csv).
5. Validation of empty files and files exceeding maximum allowed size.
6. Safe handling of corrupted/malformed PDF, DOCX, and TXT files.
7. Text normalization (whitespace, null byte removal, CRLF conversion).
8. Preservation of ExtractedDocument schema and provenance metadata.
"""

import io
import pytest
import fitz  # PyMuPDF
import docx  # python-docx

from app.services.document_extractor import (
    DocumentExtractor,
    DocumentExtractionError,
    UnsupportedFileTypeError,
    FileValidationError,
    clean_text,
)
from app.schemas.chunk import ExtractedDocument


def create_in_memory_pdf(pages_text: list[str]) -> bytes:
    """Helper creating a real PDF in memory with PyMuPDF."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_in_memory_docx(paragraphs: list[str], with_page_break: bool = False) -> bytes:
    """Helper creating a real DOCX in memory with python-docx."""
    doc = docx.Document()
    for idx, text in enumerate(paragraphs):
        doc.add_paragraph(text)
        if with_page_break and idx < len(paragraphs) - 1:
            doc.add_page_break()
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


@pytest.fixture
def extractor():
    return DocumentExtractor(max_file_size_bytes=1024 * 1024)  # 1MB limit for tests


# -----------------------------------------------------------------------------
# PDF Extraction Tests
# -----------------------------------------------------------------------------
def test_pdf_extraction_page_traceability(extractor):
    """Verify PDF extraction preserves exact 1-based page numbers."""
    page1_text = "Page 1: Welcome to CampusMind AI University Knowledge Assistant."
    page2_text = "Page 2: Computer Science curriculum and grading policies."
    pdf_bytes = create_in_memory_pdf([page1_text, page2_text])

    extracted = extractor.extract_document(
        file_input=pdf_bytes,
        filename="Handbook.pdf",
        document_id="doc-pdf-01",
    )

    assert isinstance(extracted, ExtractedDocument)
    assert extracted.document_id == "doc-pdf-01"
    assert extracted.document_name == "Handbook.pdf"
    assert len(extracted.pages) == 2

    # Check page numbers and contents
    assert extracted.pages[0].page_number == 1
    assert "Welcome to CampusMind" in extracted.pages[0].text

    assert extracted.pages[1].page_number == 2
    assert "Computer Science curriculum" in extracted.pages[1].text

    assert extracted.metadata["file_type"] == "pdf"
    assert extracted.metadata["page_count"] == 2


# -----------------------------------------------------------------------------
# DOCX Extraction Tests
# -----------------------------------------------------------------------------
def test_docx_extraction_with_breaks(extractor):
    """Verify DOCX extraction captures paragraphs and tracks page breaks."""
    docx_bytes = create_in_memory_docx(
        paragraphs=["Section 1: Admission requirements.", "Section 2: Tuition and fees."],
        with_page_break=True,
    )

    extracted = extractor.extract_document(
        file_input=docx_bytes,
        filename="Admission.docx",
    )

    assert isinstance(extracted, ExtractedDocument)
    assert extracted.document_name == "Admission.docx"
    assert len(extracted.pages) == 2
    assert extracted.pages[0].page_number == 1
    assert "Admission requirements" in extracted.pages[0].text
    assert extracted.pages[1].page_number == 2
    assert "Tuition and fees" in extracted.pages[1].text
    assert extracted.metadata["has_explicit_page_breaks"] is True


def test_docx_extraction_without_breaks(extractor):
    """Verify DOCX without hard page breaks extracts into a single continuous page."""
    docx_bytes = create_in_memory_docx(
        paragraphs=["Paragraph A.", "Paragraph B."],
        with_page_break=False,
    )

    extracted = extractor.extract_document(
        file_input=docx_bytes,
        filename="Notes.docx",
    )

    assert len(extracted.pages) == 1
    assert extracted.pages[0].page_number == 1
    assert "Paragraph A." in extracted.pages[0].text
    assert "Paragraph B." in extracted.pages[0].text
    assert extracted.metadata["has_explicit_page_breaks"] is False


# -----------------------------------------------------------------------------
# TXT Extraction Tests
# -----------------------------------------------------------------------------
def test_txt_extraction_single_page(extractor):
    """Verify TXT files are cleanly parsed as a single page."""
    txt_content = "Campus library opens from 8:00 AM to 10:00 PM on weekdays.\r\nClosed on Sundays."
    txt_bytes = txt_content.encode("utf-8")

    extracted = extractor.extract_document(
        file_input=txt_bytes,
        filename="LibraryHours.txt",
    )

    assert len(extracted.pages) == 1
    assert extracted.pages[0].page_number == 1
    assert "8:00 AM to 10:00 PM" in extracted.pages[0].text
    # Verify CRLF was normalized
    assert "\r" not in extracted.pages[0].text
    assert extracted.metadata["file_type"] == "txt"


# -----------------------------------------------------------------------------
# Validation & Error Handling Tests
# -----------------------------------------------------------------------------
def test_reject_unsupported_extensions(extractor):
    """Verify unsupported extensions (.exe, .csv, .py) are rejected."""
    with pytest.raises(UnsupportedFileTypeError, match="Unsupported file format"):
        extractor.extract_document(b"malicious code", filename="script.exe")

    with pytest.raises(UnsupportedFileTypeError, match="Unsupported file format"):
        extractor.extract_document(b"a,b,c\n1,2,3", filename="data.csv")

    with pytest.raises(UnsupportedFileTypeError, match="Missing extension"):
        extractor.extract_document(b"no extension data", filename="README")


def test_reject_empty_file(extractor):
    """Verify empty file inputs (0 bytes) raise FileValidationError."""
    with pytest.raises(FileValidationError, match="is empty"):
        extractor.extract_document(b"", filename="Empty.pdf")


def test_file_size_limit_enforced():
    """Verify files larger than max_file_size_bytes are rejected."""
    strict_extractor = DocumentExtractor(max_file_size_bytes=50)  # 50 bytes limit
    large_payload = b"A" * 100

    with pytest.raises(FileValidationError, match="exceeds limit"):
        strict_extractor.extract_document(large_payload, filename="Oversized.txt")


def test_corrupted_file_handling(extractor):
    """Verify malformed/corrupted files raise DocumentExtractionError cleanly."""
    garbage_bytes = b"This is not a real PDF structure"
    with pytest.raises(DocumentExtractionError, match="Malformed or corrupt PDF"):
        extractor.extract_document(garbage_bytes, filename="Corrupt.pdf")

    with pytest.raises(DocumentExtractionError, match="Malformed or corrupt DOCX"):
        extractor.extract_document(garbage_bytes, filename="Corrupt.docx")


# -----------------------------------------------------------------------------
# Text Cleaning Tests
# -----------------------------------------------------------------------------
def test_clean_text_normalization():
    """Verify clean_text strips null bytes, excessive empty lines, and non-breaking spaces."""
    messy_input = "Header line\x00with null.\r\n\r\n\r\n\r\nParagraph with\xa0non-breaking space.\n"
    cleaned = clean_text(messy_input)

    assert "\x00" not in cleaned
    assert "\r" not in cleaned
    assert "\xa0" not in cleaned
    assert "Header line with null." in cleaned
    assert "\n\n\n" not in cleaned  # collapsed extra newlines

