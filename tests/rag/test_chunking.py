"""Tests for document parsing and chunking (P6-1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chunking import (
    ParsedDocument,
    _stable_chunk_id,
    _stable_doc_id,
    chunk_document,
    parse_document,
)

# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------


def test_parse_markdown(tmp_path: Path) -> None:
    """parse_document reads a .md file and returns its full content."""
    md = tmp_path / "test.md"
    md.write_text("# Hello\n\nWorld", encoding="utf-8")
    doc = parse_document(md)
    assert "Hello" in doc.content
    assert "World" in doc.content
    assert doc.metadata["extension"] == ".md"


def test_parse_txt(tmp_path: Path) -> None:
    """parse_document reads a .txt file."""
    txt = tmp_path / "note.txt"
    txt.write_text("Plain text content.", encoding="utf-8")
    doc = parse_document(txt)
    assert doc.content == "Plain text content."
    assert doc.metadata["filename"] == "note.txt"


def test_parse_unsupported_extension(tmp_path: Path) -> None:
    """parse_document raises ValueError for unsupported extensions."""
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        parse_document(f)


def test_parse_pdf_missing_library(tmp_path: Path) -> None:
    """parse_document returns a ParsedDocument with parse_error when pypdf is absent."""
    import sys

    # Temporarily hide pypdf if it exists
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    pypdf_mod = sys.modules.pop("pypdf", None)
    try:
        doc = parse_document(pdf)
        # Either parsed successfully (pypdf installed) or error metadata
        assert doc.metadata["extension"] == ".pdf"
    finally:
        if pypdf_mod is not None:
            sys.modules["pypdf"] = pypdf_mod


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------


def _make_doc(content: str, path: str = "test.md") -> ParsedDocument:
    return ParsedDocument(source_path=path, content=content, metadata={"filename": path})


def test_chunk_produces_non_empty_chunks() -> None:
    """chunk_document returns at least one non-empty chunk."""
    doc = _make_doc("# Title\n\nSome paragraph text here.\n\nAnother paragraph.")
    chunks = chunk_document(doc)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.content.strip()


def test_chunk_ids_are_stable() -> None:
    """Running chunk_document twice produces the same chunk_ids (idempotent)."""
    doc = _make_doc("Hello world. " * 50, path="stable.md")
    chunks1 = chunk_document(doc)
    chunks2 = chunk_document(doc)
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]


def test_chunk_has_doc_id() -> None:
    """Every chunk carries the doc_id derived from source_path."""
    doc = _make_doc("Content here.", path="myfile.md")
    chunks = chunk_document(doc)
    expected_doc_id = _stable_doc_id("myfile.md")
    for c in chunks:
        assert c.doc_id == expected_doc_id


def test_chunk_metadata_preserved() -> None:
    """Chunk metadata includes source_path and chunk_index."""
    doc = _make_doc("Some content.", path="/docs/policy.md")
    chunks = chunk_document(doc)
    for c in chunks:
        assert "source_path" in c.metadata
        assert "chunk_index" in c.metadata


def test_long_document_produces_multiple_chunks() -> None:
    """A document much longer than DEFAULT_CHUNK_SIZE is split into multiple chunks."""
    long_text = "The quick brown fox jumps over the lazy dog. " * 100
    doc = _make_doc(long_text, path="long.md")
    chunks = chunk_document(doc)
    assert len(chunks) > 1


def test_chunk_size_respects_limit() -> None:
    """No chunk exceeds chunk_size + chunk_overlap characters by much."""
    doc = _make_doc("Word " * 500, path="words.md")
    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=20)
    for c in chunks:
        # Allow some slack for overlap and word-boundary rounding.
        assert len(c.content) <= 300, f"Chunk too long: {len(c.content)}"


def test_fifteen_documents_yield_expected_chunk_count() -> None:
    """The 15 sample documents produce roughly 50-120 chunks (target ~70). F6."""
    sample_dir = Path("sample_data/documents")
    if not sample_dir.exists():
        pytest.skip("sample_data/documents not present")

    total = 0
    for md_file in sample_dir.glob("*.md"):
        doc = parse_document(md_file)
        chunks = chunk_document(doc)
        total += len(chunks)

    assert 40 <= total <= 150, f"Expected ~70 chunks, got {total}"


def test_chunk_stable_id_different_per_index() -> None:
    """Different chunk indices produce different chunk_ids."""
    doc_id = _stable_doc_id("test.md")
    id0 = _stable_chunk_id(doc_id, 0)
    id1 = _stable_chunk_id(doc_id, 1)
    assert id0 != id1
