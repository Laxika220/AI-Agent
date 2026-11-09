from pathlib import Path

import pytest

from app.utils.chunking import chunk_text
from app.utils.embeddings import maximal_marginal_relevance
from app.utils.extraction import extract_text


def test_chunking_respects_size_and_overlap() -> None:
    text = " ".join(f"Sentence number {i} talks about agents." for i in range(300))
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    # overlap means some text is repeated across neighbouring chunks
    assert sum(len(c) for c in chunks) > len(text)


def test_chunking_empty_text() -> None:
    assert chunk_text("   ") == []


def test_chunking_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=100, chunk_overlap=100)


def test_mmr_prefers_diverse_results() -> None:
    query = [1.0, 0.0]
    candidates = [[1.0, 0.0], [0.99, 0.01], [0.7, 0.7]]
    # Pure relevance picks the two near-duplicates; MMR swaps in the diverse one.
    assert maximal_marginal_relevance(query, candidates, k=2, lambda_mult=1.0) == [0, 1]
    assert maximal_marginal_relevance(query, candidates, k=2, lambda_mult=0.3) == [0, 2]


def test_mmr_handles_edge_cases() -> None:
    assert maximal_marginal_relevance([1.0], [], k=3) == []
    assert maximal_marginal_relevance([1.0, 0.0], [[1.0, 0.0]], k=5) == [0]


def test_extract_text_from_markdown(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Title\n\nHello world", encoding="utf-8")
    assert extract_text(path) == "# Title\n\nHello world"
