"""Recursive character text chunking."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Prefer splitting on structure (headings/paragraphs), then sentences, then words.
_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks of roughly `chunk_size` characters."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_SEPARATORS,
        length_function=len,
        strip_whitespace=True,
    )
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]
