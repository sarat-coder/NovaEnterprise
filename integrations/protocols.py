"""DocumentSource protocol — the integration point for external content systems (P9-3).

Real implementations (Confluence, SharePoint, Google Drive, ticketing) plug in here.
The demo never requires them: mock adapters suffice for all tests and `make demo`.

Usage pattern:
    source: DocumentSource = ConfluenceMockAdapter()
    for doc_ref in source.list_documents():
        content = source.fetch_content(doc_ref.source_id)
        ingest_bytes(content, doc_ref.filename, session)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class DocumentReference:
    """A pointer to a document in an external system."""

    source_id: str
    filename: str
    title: str = ""
    source_type: str = "unknown"  # confluence / sharepoint / drive / ticket / local
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DocumentSource(Protocol):
    """Protocol that every external document source must satisfy.

    Adapters are read-only: they discover and fetch documents, never write.
    The demo uses mock adapters; real implementations swap in by config.
    """

    @property
    def source_name(self) -> str:
        """Human-readable name shown in the UI (e.g. 'Confluence Wiki')."""
        ...

    def list_documents(self, limit: int = 100) -> list[DocumentReference]:
        """Return up to *limit* document references available from this source."""
        ...

    def fetch_content(self, source_id: str) -> bytes:
        """Fetch the raw content (bytes) of a document by its source id.

        The returned bytes must be in one of the allowed ingest formats:
        .md, .txt, or .pdf.
        """
        ...

    def health(self) -> dict[str, str]:
        """Return {'status': 'ok'|'degraded'|'error', 'detail': '...'}."""
        ...
