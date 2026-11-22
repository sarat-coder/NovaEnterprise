"""Ingest pipeline: parse → chunk → extract → index (P9-2).

Satisfies F13: md / txt / PDF → chunk → extract entities + relationships →
index into vector store + DB + graph.

Design:
- Guardrails run on every chunk before it reaches any store.
- DocumentRecord + DocumentChunk rows written to the DB for browsing.
- Entities and relationships extracted and upserted into the graph store.
- Chunks embedded and indexed into the vector store.
- Re-running is safe: existing document records are skipped if status="indexed".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.guardrails import process_chunk, scan_for_injection
from app.core.logging import get_logger
from rag.chunking import DocumentChunk, chunk_document, parse_document
from rag.extraction import extract_entities
from rag.graph_store import get_graph_store
from rag.vector_store import get_vector_store

logger = get_logger(__name__)

# Extension allowlist (N7)
ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def ingest_file(
    path: str | Path,
    session: Any,  # SQLAlchemy Session — typed as Any to avoid importing here
    uploaded_by: str = "system",
    *,
    force: bool = False,
) -> str:
    """Ingest a single file: parse → chunk → guardrail → index.

    Returns the document id (a stable UUID based on the file path).
    If the document is already indexed and force=False, returns existing id.
    Raises ValueError for unsupported extensions.
    """
    from app.models.research import (  # noqa: PLC0415
        DocumentChunk as DBChunk,
    )
    from app.models.research import (
        DocumentRecord,
    )
    from app.repositories.document_repo import DocumentRepository  # noqa: PLC0415

    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported extension {suffix!r}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    repo = DocumentRepository(session)

    # Build a stable doc id from the path so re-runs are idempotent.
    from rag.chunking import _stable_doc_id  # noqa: PLC0415

    doc_id = _stable_doc_id(str(p))

    existing = repo.get_by_id(doc_id)
    if existing and existing.status == "indexed" and not force:
        logger.info("document already indexed, skipping", extra={"doc_id": doc_id})
        return doc_id

    # --- Parse ---
    parsed = parse_document(p)

    # Scan the whole document text for injection before chunking.
    full_scan = scan_for_injection(parsed.content)
    flagged = full_scan.flagged
    flag_reason = full_scan.reason if flagged else None
    if flagged:
        logger.warning(
            "injection detected in document",
            extra={"path": str(p), "reasons": full_scan.reasons},
        )

    # --- Chunk ---
    raw_chunks = chunk_document(parsed)

    # --- Create or update DB record ---
    if existing:
        existing.status = "indexing"
        existing.flagged = flagged
        existing.flag_reason = flag_reason
        session.flush()
    else:
        doc_record = DocumentRecord(
            id=doc_id,
            filename=p.name,
            source_path=str(p),
            content_type=_content_type(suffix),
            size_bytes=p.stat().st_size if p.exists() else 0,
            status="indexing",
            chunk_count=len(raw_chunks),
            uploaded_by=uploaded_by,
            flagged=flagged,
            flag_reason=flag_reason,
        )
        repo.add(doc_record)

    # --- Guardrail + store chunks ---
    vector_store = get_vector_store()
    graph_store = get_graph_store()
    processed_chunks: list[DocumentChunk] = []

    for raw in raw_chunks:
        gr = process_chunk(raw.content)
        safe_chunk = DocumentChunk(
            chunk_id=raw.chunk_id,
            doc_id=raw.doc_id,
            content=gr.sanitized_text,
            metadata={**raw.metadata, "flagged": gr.flagged},
        )
        processed_chunks.append(safe_chunk)

        # Write to DB
        db_chunk = DBChunk(
            id=raw.chunk_id,
            document_id=doc_id,
            chunk_index=raw.metadata.get("chunk_index", 0),
            content=gr.sanitized_text,
            metadata_json=json.dumps(
                {**raw.metadata, "flagged": gr.flagged, "flag_reasons": gr.reasons}
            ),
        )
        try:
            session.merge(db_chunk)
        except Exception:
            session.rollback()
            session.add(db_chunk)
        session.flush()

        # Entity extraction on the original (pre-wrap) text
        extraction = extract_entities(raw.content, doc_id)
        for node in extraction.nodes:
            graph_store.add_node(node)
        for edge in extraction.edges:
            try:
                graph_store.add_edge(edge)
            except Exception as exc:
                logger.debug("edge add error (likely duplicate)", extra={"exc": str(exc)})

    # --- Embed and index chunks into vector store ---
    try:
        vector_store.add_chunks(processed_chunks)
    except Exception as exc:
        logger.error("vector store indexing failed", extra={"exc": str(exc)})

    # --- Update DB record status ---
    final_record = repo.get_by_id(doc_id)
    if final_record:
        final_record.status = "indexed"
        final_record.chunk_count = len(processed_chunks)
        session.flush()

    logger.info(
        "document indexed",
        extra={
            "doc_id": doc_id,
            "chunks": len(processed_chunks),
            "flagged": flagged,
        },
    )
    return doc_id


def ingest_directory(
    directory: str | Path,
    session: Any,
    uploaded_by: str = "system",
    *,
    force: bool = False,
) -> list[str]:
    """Ingest all supported files in a directory.

    Returns the list of document ids (skips unsupported extensions silently).
    """
    d = Path(directory)
    if not d.is_dir():
        raise ValueError(f"Not a directory: {d}")

    doc_ids: list[str] = []
    for p in sorted(d.iterdir()):
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        try:
            doc_id = ingest_file(p, session, uploaded_by=uploaded_by, force=force)
            doc_ids.append(doc_id)
        except Exception as exc:
            logger.error(
                "failed to ingest file",
                extra={"path": str(p), "error": str(exc)},
            )
    return doc_ids


def ingest_bytes(
    content: bytes,
    filename: str,
    session: Any,
    uploaded_by: str = "system",
) -> str:
    """Ingest a file provided as raw bytes (uploaded via HTTP).

    Writes a temporary file, ingests it, and cleans up.
    Returns the document id.
    """
    import tempfile  # noqa: PLC0415

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported extension {suffix!r}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        doc_id = ingest_file(tmp_path, session, uploaded_by=uploaded_by)
    finally:
        tmp_path.unlink(missing_ok=True)

    return doc_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_type(suffix: str) -> str:
    return {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


# ---------------------------------------------------------------------------
# CLI entry point (make ingest)
# ---------------------------------------------------------------------------


def _cli_ingest() -> None:
    """Ingest sample_data/documents/ — called by `make ingest`."""
    import os  # noqa: PLC0415
    import sys  # noqa: PLC0415

    # Ensure backend is on PYTHONPATH
    here = Path(__file__).parent.parent
    backend = here / "backend"
    sys.path.insert(0, str(backend))

    os.environ.setdefault("LLM_PROVIDER", "fake")
    os.environ.setdefault("VECTOR_STORE", "memory")
    os.environ.setdefault("GRAPH_STORE", "memory")

    from app.core.db import get_session_factory, init_db  # noqa: PLC0415

    init_db()
    factory = get_session_factory()

    docs_dir = here / "sample_data" / "documents"
    print(f"Ingesting documents from {docs_dir} ...")

    with factory() as session:
        ids = ingest_directory(docs_dir, session, force=True)
        session.commit()

    print(f"Done. Indexed {len(ids)} document(s).")


if __name__ == "__main__":
    _cli_ingest()
