"""Plain-text extraction for supported upload formats (PDF, DOCX, TXT, MD)."""

from pathlib import Path

from app.core.errors import BadRequestError


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def _extract_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def _extract_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_text(path: Path) -> str:
    """Extract text from a file based on its extension.

    Raises:
        BadRequestError: for unsupported extensions.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(path)
    elif suffix == ".docx":
        text = _extract_docx(path)
    elif suffix in {".txt", ".md"}:
        text = _extract_text(path)
    else:
        raise BadRequestError(f"Unsupported file type: {suffix}")
    # Normalise NUL bytes that some PDFs emit; they break downstream tokenizers.
    return text.replace("\x00", "").strip()
