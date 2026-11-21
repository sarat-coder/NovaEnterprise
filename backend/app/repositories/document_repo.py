from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research import ApprovalRequest, DocumentChunk, DocumentRecord


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[DocumentRecord]:
        return list(self._session.execute(select(DocumentRecord)).scalars())

    def get_by_id(self, doc_id: str) -> DocumentRecord | None:
        return self._session.get(DocumentRecord, doc_id)

    def get_by_filename(self, filename: str) -> DocumentRecord | None:
        stmt = select(DocumentRecord).where(DocumentRecord.filename == filename)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_flagged(self) -> list[DocumentRecord]:
        stmt = select(DocumentRecord).where(DocumentRecord.flagged.is_(True))
        return list(self._session.execute(stmt).scalars())

    def add(self, doc: DocumentRecord) -> DocumentRecord:
        self._session.add(doc)
        self._session.flush()
        return doc

    def add_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        self._session.add(chunk)
        self._session.flush()
        return chunk

    def get_chunks(self, document_id: str) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        return list(self._session.execute(stmt).scalars())

    def count(self) -> int:
        return self._session.query(DocumentRecord).count()

    def create_approval(self, req: ApprovalRequest) -> ApprovalRequest:
        self._session.add(req)
        self._session.flush()
        return req
