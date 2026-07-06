"""Extracts plain text from uploaded resume files (PDF / DOCX)."""
import io
from pathlib import Path

import docx
from pypdf import PdfReader

from services.exceptions import TextExtractionError, UnsupportedFileTypeError


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text).strip()
        if not text:
            raise TextExtractionError(
                "No extractable text found in the PDF.",
                details="The PDF may be a scanned image without a text layer.",
            )
        return text
    except TextExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError("Failed to read the PDF file.", details=str(exc)) from exc


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.append(cell.text)
        text = "\n".join(p for p in paragraphs if p and p.strip()).strip()
        if not text:
            raise TextExtractionError("No extractable text found in the DOCX file.")
        return text
    except TextExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError("Failed to read the DOCX file.", details=str(exc)) from exc


def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_bytes)
    if suffix == ".docx":
        return extract_text_from_docx(file_bytes)
    raise UnsupportedFileTypeError(
        f"Unsupported file type '{suffix}'. Only .pdf and .docx are supported."
    )
