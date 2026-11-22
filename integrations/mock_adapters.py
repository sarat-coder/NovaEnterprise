"""Mock DocumentSource adapters (P9-3).

These adapters return pre-canned document references without network access.
They are used in tests and in `make demo`.  Real adapters (Confluence, SharePoint,
Google Drive, Jira) can be swapped in by replacing the adapter class.
"""

from __future__ import annotations

from pathlib import Path

from integrations.protocols import DocumentReference

# Sample documents directory, two levels above this file.
_SAMPLE_DOCS = Path(__file__).parent.parent / "sample_data" / "documents"


class LocalDirectoryAdapter:
    """Read documents from a local directory — the default for the demo.

    Implements DocumentSource by reading .md / .txt / .pdf files from a folder.
    """

    source_name = "Local Document Store"

    def __init__(self, directory: str | Path | None = None) -> None:
        self._dir = Path(directory) if directory else _SAMPLE_DOCS

    def list_documents(self, limit: int = 100) -> list[DocumentReference]:
        refs: list[DocumentReference] = []
        allowed = {".md", ".txt", ".pdf"}
        for p in sorted(self._dir.iterdir()):
            if p.suffix.lower() not in allowed:
                continue
            refs.append(
                DocumentReference(
                    source_id=str(p),
                    filename=p.name,
                    title=p.stem.replace("-", " ").title(),
                    source_type="local",
                    metadata={"path": str(p), "size_bytes": p.stat().st_size},
                )
            )
            if len(refs) >= limit:
                break
        return refs

    def fetch_content(self, source_id: str) -> bytes:
        p = Path(source_id)
        if not p.exists():
            raise FileNotFoundError(f"Document not found: {source_id}")
        return p.read_bytes()

    def health(self) -> dict[str, str]:
        if self._dir.is_dir():
            allowed = {".md", ".txt", ".pdf"}
            count = sum(1 for p in self._dir.iterdir() if p.suffix.lower() in allowed)
            return {"status": "ok", "detail": f"local ({count} documents)"}
        return {"status": "error", "detail": f"directory not found: {self._dir}"}


class ConfluenceMockAdapter:
    """Mock Confluence adapter — returns a fixed set of stub documents.

    In a real deployment this would call the Confluence REST API.
    """

    source_name = "Confluence Wiki (mock)"

    _STUBS = [
        DocumentReference(
            source_id="confluence://space/ENG/page/1001",
            filename="engineering-handbook.md",
            title="Engineering Handbook",
            source_type="confluence",
            metadata={"space": "ENG", "page_id": "1001"},
        ),
        DocumentReference(
            source_id="confluence://space/OPS/page/2001",
            filename="ops-runbooks.md",
            title="Ops Runbooks",
            source_type="confluence",
            metadata={"space": "OPS", "page_id": "2001"},
        ),
    ]

    def list_documents(self, limit: int = 100) -> list[DocumentReference]:
        return self._STUBS[:limit]

    def fetch_content(self, source_id: str) -> bytes:
        for stub in self._STUBS:
            if stub.source_id == source_id:
                return f"# {stub.title}\n\nMock content from {source_id}".encode()
        raise KeyError(f"Document not found in mock: {source_id}")

    def health(self) -> dict[str, str]:
        return {"status": "ok", "detail": "confluence mock (no credentials needed)"}


class SharePointMockAdapter:
    """Mock SharePoint adapter."""

    source_name = "SharePoint (mock)"

    _STUBS = [
        DocumentReference(
            source_id="sharepoint://sites/Engineering/documents/api-guidelines.md",
            filename="api-guidelines.md",
            title="API Design Guidelines",
            source_type="sharepoint",
        ),
    ]

    def list_documents(self, limit: int = 100) -> list[DocumentReference]:
        return self._STUBS[:limit]

    def fetch_content(self, source_id: str) -> bytes:
        for stub in self._STUBS:
            if stub.source_id == source_id:
                return f"# {stub.title}\n\nMock content from {source_id}".encode()
        raise KeyError(f"Document not found in mock: {source_id}")

    def health(self) -> dict[str, str]:
        return {"status": "ok", "detail": "sharepoint mock (no credentials needed)"}


class TicketingMockAdapter:
    """Mock ticketing adapter (Jira / Linear stubs)."""

    source_name = "Ticketing System (mock)"

    def list_documents(self, limit: int = 100) -> list[DocumentReference]:
        return []

    def fetch_content(self, source_id: str) -> bytes:
        raise KeyError(f"No tickets in mock: {source_id}")

    def health(self) -> dict[str, str]:
        return {"status": "ok", "detail": "ticketing mock (no credentials needed)"}
