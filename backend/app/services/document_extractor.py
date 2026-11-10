"""CampusMind AI - Document Extractor Service.

Extracts text, normalizes content, and validates PDF, DOCX, and TXT files.

Responsibilities:
1. clean_text(): Normalizes whitespace, replaces null characters, and cleans text.
Class DocumentExtractor:
2. DocumentExtractor.__init__(): Initializes maximum allowable file size limit.
3. DocumentExtractor._read_and_validate_bytes(): Validates non-empty content, size bounds, and file extension.
4. DocumentExtractor.extract_document(): Main dispatcher extracting structured pages from valid documents.
5. DocumentExtractor._extract_pdf(): Extracts 1-based page text from PDF files using PyMuPDF.
6. DocumentExtractor._extract_docx(): Extracts structured paragraphs and tables from DOCX files.
7. DocumentExtractor._extract_txt(): Decodes text documents supporting UTF-8 and Latin-1 fallbacks.
"""

import io
import os
import re
import uuid
import logging
from typing import Optional, Union, BinaryIO, List

import fitz  # PyMuPDF
import docx  # python-docx

from app.schemas.chunk import ExtractedDocument, ExtractedPage

logger = logging.getLogger(__name__)

DEFAULT_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB default limit
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# Base exception for document extraction failures.
class DocumentExtractionError(Exception):
    pass


# Raised when an unsupported file extension or format is supplied.
class UnsupportedFileTypeError(DocumentExtractionError):
    pass


# Raised when file validation (size, content, empty check) fails.
class FileValidationError(DocumentExtractionError):
    pass


# Cleans and normalizes extracted text: - Strips null bytes and control characters (excluding standard whitespace) - Normalizes Windows CRLF to LF - Collapses multiple blank lines while preserving paragraph boundaries - Strips trailing/leading whitespace.
def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    # Replace null characters with a space
    text = raw_text.replace("\x00", " ")
    # Normalize CRLF to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking spaces with standard space
    text = text.replace("\xa0", " ")
    # Collapse multiple inline spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3 or more newlines into 2 (clean paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip whitespace on each line while preserving indentation structure
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(lines).strip()
    return cleaned


# Extracts structured pages and text from PDF, DOCX, and TXT files.
class DocumentExtractor:

    # Initializes DocumentExtractor.
    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE):
        self.max_file_size_bytes = max_file_size_bytes

    # Reads input into raw bytes and validates file size, non-empty content, and extension.
    def _read_and_validate_bytes(
        self,
        file_input: Union[str, bytes, BinaryIO],
        filename: Optional[str] = None,
    ) -> tuple[bytes, str]:
        raw_bytes: bytes = b""
        resolved_filename = filename or ""

        if isinstance(file_input, str):
            # Path to file
            if not os.path.exists(file_input):
                raise FileValidationError(f"File not found: {file_input}")
            if not resolved_filename:
                resolved_filename = os.path.basename(file_input)
            size = os.path.getsize(file_input)
            if size == 0:
                raise FileValidationError(f"File '{resolved_filename}' is empty (0 bytes).")
            if size > self.max_file_size_bytes:
                raise FileValidationError(
                    f"File '{resolved_filename}' exceeds maximum allowed size of {self.max_file_size_bytes} bytes."
                )
            with open(file_input, "rb") as f:
                raw_bytes = f.read()

        elif isinstance(file_input, bytes):
            raw_bytes = file_input

        elif hasattr(file_input, "read"):
            # File-like stream
            raw_bytes = file_input.read()

        else:
            raise FileValidationError(f"Unsupported file input type: {type(file_input)}")

        # Check byte size
        if len(raw_bytes) == 0:
            raise FileValidationError(f"File '{resolved_filename}' is empty (0 bytes).")

        if len(raw_bytes) > self.max_file_size_bytes:
            raise FileValidationError(
                f"File '{resolved_filename}' size ({len(raw_bytes)} bytes) exceeds limit of {self.max_file_size_bytes} bytes."
            )

        # Validate extension
        _, ext = os.path.splitext(resolved_filename.lower())
        if not ext:
            raise UnsupportedFileTypeError(
                f"Cannot determine file type for '{resolved_filename}'. Missing extension."
            )
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file format '{ext}' for file '{resolved_filename}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return raw_bytes, ext

    # Extracts clean text and pages from a PDF, DOCX, or TXT file.
    def extract_document(
        self,
        file_input: Union[str, bytes, BinaryIO],
        filename: str,
        document_id: Optional[str] = None,
    ) -> ExtractedDocument:
        raw_bytes, ext = self._read_and_validate_bytes(file_input, filename=filename)
        doc_id = document_id or str(uuid.uuid4())

        try:
            if ext == ".pdf":
                pages, meta = self._extract_pdf(raw_bytes, filename)
            elif ext == ".docx":
                pages, meta = self._extract_docx(raw_bytes, filename)
            elif ext == ".txt":
                pages, meta = self._extract_txt(raw_bytes, filename)
            else:
                raise UnsupportedFileTypeError(f"Unsupported extension: {ext}")

            return ExtractedDocument(
                document_id=doc_id,
                document_name=filename,
                pages=pages,
                metadata=meta,
            )

        except (UnsupportedFileTypeError, FileValidationError):
            raise
        except Exception as e:
            logger.error("Failed to extract document '%s': %s", filename, e)
            raise DocumentExtractionError(f"Extraction error for '{filename}': {str(e)}") from e

    # Extracts text from PDF preserving 1-based page numbers via PyMuPDF.
    def _extract_pdf(self, raw_bytes: bytes, filename: str) -> tuple[List[ExtractedPage], dict]:
        try:
            pdf_doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as e:
            raise DocumentExtractionError(f"Malformed or corrupt PDF file '{filename}': {e}") from e

        if pdf_doc.page_count == 0:
            raise DocumentExtractionError(f"PDF file '{filename}' has no pages.")

        pages: List[ExtractedPage] = []
        total_chars = 0

        for page_idx in range(pdf_doc.page_count):
            page = pdf_doc[page_idx]
            raw_text = page.get_text("text") or ""
            cleaned = clean_text(raw_text)
            if cleaned:
                pages.append(ExtractedPage(page_number=page_idx + 1, text=cleaned))
                total_chars += len(cleaned)

        metadata = {
            "file_type": "pdf",
            "page_count": pdf_doc.page_count,
            "extracted_page_count": len(pages),
            "character_count": total_chars,
            "is_encrypted": pdf_doc.is_encrypted,
        }
        return pages, metadata

    # Extracts text from DOCX using python-docx.
    def _extract_docx(self, raw_bytes: bytes, filename: str) -> tuple[List[ExtractedPage], dict]:
        try:
            docx_file = io.BytesIO(raw_bytes)
            doc = docx.Document(docx_file)
        except Exception as e:
            raise DocumentExtractionError(f"Malformed or corrupt DOCX file '{filename}': {e}") from e

        pages: List[ExtractedPage] = []
        current_page_text: List[str] = []
        page_num = 1
        has_explicit_page_breaks = False

        for paragraph in doc.paragraphs:
            text = paragraph.text
            # Check for explicit page break in runs
            is_break = False
            for run in paragraph.runs:
                if 'lastRenderedPageBreak' in run._r.xml or 'w:br w:type="page"' in run._r.xml:
                    is_break = True
                    has_explicit_page_breaks = True
                    break

            if is_break and current_page_text:
                joined = clean_text("\n".join(current_page_text))
                if joined:
                    pages.append(ExtractedPage(page_number=page_num, text=joined))
                    page_num += 1
                current_page_text = []

            if text.strip():
                current_page_text.append(text)

        # Include remaining text
        if current_page_text:
            joined = clean_text("\n".join(current_page_text))
            if joined:
                pages.append(ExtractedPage(page_number=page_num, text=joined))

        # Also extract table text into the document if present
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_str = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_str:
                    table_texts.append(row_str)

        if table_texts and pages:
            # Append tables to the last page or create supplementary page
            table_content = clean_text("\n".join(table_texts))
            if table_content:
                pages[-1].text += f"\n\n[Tables]\n{table_content}"
        elif table_texts and not pages:
            pages.append(ExtractedPage(page_number=1, text=clean_text("\n".join(table_texts))))

        metadata = {
            "file_type": "docx",
            "has_explicit_page_breaks": has_explicit_page_breaks,
            "section_count": len(doc.sections),
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
            "extracted_page_count": len(pages),
        }
        return pages, metadata

    # Extracts text from TXT files, trying UTF-8, then CP1252/Latin-1 fallbacks.
    def _extract_txt(self, raw_bytes: bytes, filename: str) -> tuple[List[ExtractedPage], dict]:
        text = ""
        encoding_used = "utf-8"
        for enc in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
            try:
                text = raw_bytes.decode(enc)
                encoding_used = enc
                break
            except UnicodeDecodeError:
                continue

        if not text:
            raise DocumentExtractionError(f"Unable to decode text file '{filename}' with supported encodings.")

        cleaned = clean_text(text)
        pages = [ExtractedPage(page_number=1, text=cleaned)] if cleaned else []

        metadata = {
            "file_type": "txt",
            "encoding": encoding_used,
            "character_count": len(cleaned),
            "extracted_page_count": len(pages),
        }
        return pages, metadata
