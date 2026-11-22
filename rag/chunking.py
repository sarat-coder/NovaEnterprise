"""Document parsing (md, txt, PDF) and chunking (P6-1).

Design decisions:
- Markdown headers and blank-line paragraphs are natural split points.
- Chunks carry overlap to preserve cross-boundary context.
- Each chunk gets a stable UUID based on doc id + chunk index so re-runs
  are idempotent.
- PDF needs pypdf; it falls back to empty text with a warning when missing.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParsedDocument:
    """Raw text extracted from a file."""

    source_path: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """One chunk ready to embed and store."""

    chunk_id: str
    doc_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_document(path: str | Path) -> ParsedDocument:
    """Parse a file to plain text.

    Supports .md, .txt (direct read) and .pdf (pypdf).
    Returns ParsedDocument; raises ValueError for unsupported extensions.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".md", ".txt"}:
        content = p.read_text(encoding="utf-8", errors="replace")
        return ParsedDocument(
            source_path=str(p),
            content=content,
            metadata={"filename": p.name, "extension": suffix},
        )

    if suffix == ".pdf":
        return _parse_pdf(p)

    raise ValueError(f"Unsupported file extension: {suffix!r}. Allowed: .md, .txt, .pdf")


def _parse_pdf(path: Path) -> ParsedDocument:
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ImportError:
        return ParsedDocument(
            source_path=str(path),
            content="",
            metadata={
                "filename": path.name,
                "extension": ".pdf",
                "parse_error": "pypdf not installed",
            },
        )

    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return ParsedDocument(
            source_path=str(path),
            content="\n\n".join(pages),
            metadata={"filename": path.name, "extension": ".pdf", "page_count": len(reader.pages)},
        )
    except Exception as exc:
        return ParsedDocument(
            source_path=str(path),
            content="",
            metadata={"filename": path.name, "extension": ".pdf", "parse_error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

# Default parameters match the target ≈ 70 chunks over 15 documents.
DEFAULT_CHUNK_SIZE = 512  # characters
DEFAULT_CHUNK_OVERLAP = 64  # characters


def chunk_document(
    doc: ParsedDocument,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split a parsed document into overlapping chunks.

    Strategy:
    1. Split on markdown headings (# / ## / ###) and double blank lines.
    2. If a segment still exceeds chunk_size, split further at sentence or
       word boundaries.
    3. Add overlap by prepending the tail of the previous chunk.
    4. Assign stable UUIDs derived from (source_path, chunk_index).
    """
    doc_id = _stable_doc_id(doc.source_path)
    segments = _split_into_segments(doc.content)
    chunks = _segments_to_chunks(segments, chunk_size, chunk_overlap)

    result: list[DocumentChunk] = []
    for i, text in enumerate(chunks):
        text = text.strip()
        if not text:
            continue
        chunk_id = _stable_chunk_id(doc_id, i)
        result.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                content=text,
                metadata={
                    **doc.metadata,
                    "chunk_index": i,
                    "source_path": doc.source_path,
                },
            )
        )
    return result


def _split_into_segments(text: str) -> list[str]:
    """Split on markdown headings and double blank lines."""
    # Split on markdown heading lines or two or more consecutive newlines.
    segments = re.split(r"(?m)(?=^#{1,3}\s)|\n{2,}", text)
    return [s for s in segments if s.strip()]


def _segments_to_chunks(
    segments: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Merge segments into ~chunk_size chunks with overlap."""
    chunks: list[str] = []
    current = ""

    for seg in segments:
        # If the segment alone exceeds chunk_size, split it at sentence boundaries.
        sub_parts = _split_long_segment(seg, chunk_size) if len(seg) > chunk_size else [seg]

        for part in sub_parts:
            if len(current) + len(part) + 1 <= chunk_size:
                current = (current + "\n" + part).lstrip()
            else:
                if current:
                    chunks.append(current)
                # Carry overlap from the tail of the previous chunk.
                tail = current[-chunk_overlap:] if chunk_overlap else ""
                current = (tail + "\n" + part).lstrip() if tail else part.lstrip()

    if current.strip():
        chunks.append(current)

    return chunks


def _split_long_segment(text: str, chunk_size: int) -> list[str]:
    """Split text that is too long, preferring sentence then word breaks."""
    parts: list[str] = []
    while len(text) > chunk_size:
        # Try to split at sentence boundary within the window.
        window = text[:chunk_size]
        split_at = max(
            window.rfind(". "),
            window.rfind(".\n"),
            window.rfind("? "),
            window.rfind("! "),
        )
        if split_at > chunk_size // 2:
            parts.append(text[: split_at + 1])
            text = text[split_at + 1 :].lstrip()
        else:
            # Fall back to word boundary.
            split_at = window.rfind(" ")
            if split_at > 0:
                parts.append(text[:split_at])
                text = text[split_at:].lstrip()
            else:
                parts.append(text[:chunk_size])
                text = text[chunk_size:]
    if text.strip():
        parts.append(text)
    return parts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_doc_id(source_path: str) -> str:
    """Derive a stable UUID from the file path."""
    h = hashlib.sha256(source_path.encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


def _stable_chunk_id(doc_id: str, chunk_index: int) -> str:
    """Derive a stable UUID from doc_id + chunk index."""
    h = hashlib.sha256(f"{doc_id}:{chunk_index}".encode()).hexdigest()
    return str(uuid.UUID(h[:32]))
