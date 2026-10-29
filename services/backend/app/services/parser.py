"""
RFQ document → Markdown (Plan Phase 5 step 1).

- PDF: PyMuPDF, page by page, with tables rendered as Markdown and a page marker before
  each page so extraction can cite page numbers. Scanned PDFs with no text layer fall
  back to Docling (OCR), and so does PARSER_PDF_ENGINE=docling.
- DOCX: Docling, fed from an in-memory stream.
- TXT/MD: decoded as UTF-8.

Protected files are opened with `storage.open_decrypted`, so plaintext stays in RAM.
"""

import io
import re
from dataclasses import dataclass

import pymupdf

from app.core.config import get_settings
from app.services.storage import open_decrypted

PAGE_MARKER = "[[File: {file} | Page {page}]]"
_MIN_TEXT_CHARS_PER_PAGE = 20  # below this a PDF is treated as scanned


class UnsupportedDocumentError(ValueError):
    pass


@dataclass
class ParsedDocument:
    filename: str
    markdown: str
    pages: int
    engine: str


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _pdf_page_markdown(page: pymupdf.Page) -> str:
    """Text blocks and Markdown tables in reading order (tables replace their text)."""
    tables = page.find_tables().tables
    table_rects = [pymupdf.Rect(t.bbox) for t in tables]
    items: list[tuple[float, float, str]] = [
        (t.bbox[1], t.bbox[0], t.to_markdown(clean=False)) for t in tables
    ]
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks", sort=True):
        if text.strip() and not any(
            pymupdf.Rect(x0, y0, x1, y1).intersects(r) for r in table_rects
        ):
            items.append((y0, x0, text))
    items.sort(key=lambda i: (round(i[0], 1), i[1]))
    return "\n\n".join(text.strip() for _, _, text in items)


def _parse_pdf_pymupdf(data: bytes, filename: str) -> ParsedDocument:
    parts: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for number, page in enumerate(doc, start=1):
            parts.append(PAGE_MARKER.format(file=filename, page=number))
            parts.append(_pdf_page_markdown(page))
        pages = doc.page_count
    return ParsedDocument(filename, clean_text("\n\n".join(parts)), pages, "pymupdf")


def _parse_with_docling(data: bytes, filename: str) -> ParsedDocument:
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(DocumentStream(name=filename, stream=io.BytesIO(data)))
    doc = result.document
    pages = len(doc.pages) if doc.pages else 1
    # Docling's Markdown has no page breaks; keep a file marker so citations name the file.
    header = PAGE_MARKER.format(file=filename, page="n/a")
    return ParsedDocument(
        filename, clean_text(f"{header}\n\n{doc.export_to_markdown()}"), pages, "docling"
    )


def parse_document(data: bytes, filename: str, password: str | None = None) -> ParsedDocument:
    """Raises storage.PasswordRequiredException / InvalidPasswordException for locked files."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    plain = open_decrypted(data, filename, password).getvalue()

    if ext == "pdf":
        if get_settings().PARSER_PDF_ENGINE == "docling":
            return _parse_with_docling(plain, filename)
        parsed = _parse_pdf_pymupdf(plain, filename)
        text_chars = len(re.sub(r"\[\[File:[^\]]*\]\]|\s", "", parsed.markdown))
        if parsed.pages and text_chars < _MIN_TEXT_CHARS_PER_PAGE * parsed.pages:
            return _parse_with_docling(plain, filename)  # scanned → Docling OCR
        return parsed
    if ext == "docx":
        return _parse_with_docling(plain, filename)
    if ext in {"txt", "md"}:
        text = plain.decode("utf-8", errors="replace")
        marker = PAGE_MARKER.format(file=filename, page=1)
        return ParsedDocument(filename, clean_text(f"{marker}\n\n{text}"), 1, "text")
    raise UnsupportedDocumentError(f"Unsupported RFQ document type: .{ext or '?'}")


def combine(documents: list[ParsedDocument]) -> str:
    """Single unified Markdown for the 400k-token single-pass prompt (no chunking)."""
    return "\n\n".join(d.markdown for d in documents)
