"""Approval service for admin-gated destructive actions (P9-5).

F17: Document delete creates an approval request; only admin can approve.

Design:
- Any analyst or admin can *request* a document delete.
- The document is NOT deleted until an admin approves the request.
- Approval or rejection is recorded with reviewer id and note.
- After approval, the document record status is set to "deleted"
  (physical deletion is deferred to a cleanup job in production).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.research import ApprovalRequest, DocumentRecord

logger = get_logger(__name__)


class ApprovalService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Request creation
    # ------------------------------------------------------------------

    def request_document_delete(
        self,
        document_id: str,
        requested_by: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Create a pending approval request for document deletion.

        Does NOT delete the document.  Returns the approval request.
        Raises ValueError if the document does not exist.
        """
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            raise ValueError(f"Document not found: {document_id}")

        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            action="delete_document",
            resource_type="document",
            resource_id=document_id,
            requested_by=requested_by,
            reason=reason or f"Delete document {doc.filename}",
            status="pending",
        )
        self._session.add(req)
        self._session.flush()

        logger.info(
            "approval request created",
            extra={
                "approval_id": req.id,
                "action": req.action,
                "resource_id": document_id,
                "requested_by": requested_by,
            },
        )
        return req

    # ------------------------------------------------------------------
    # Admin decisions
    # ------------------------------------------------------------------

    def approve(self, approval_id: str, reviewed_by: str, note: str = "") -> ApprovalRequest:
        """Approve a pending request and execute the approved action.

        For delete_document: sets the document status to "deleted".
        Raises ValueError if the request does not exist or is not pending.
        """
        req = self._get_pending(approval_id)
        req.status = "approved"
        req.reviewed_by = reviewed_by
        req.review_note = note
        req.reviewed_at = datetime.utcnow()
        self._session.flush()

        self._execute_approved(req)

        logger.info(
            "approval request approved",
            extra={
                "approval_id": approval_id,
                "action": req.action,
                "resource_id": req.resource_id,
                "reviewed_by": reviewed_by,
            },
        )
        return req

    def reject(self, approval_id: str, reviewed_by: str, note: str = "") -> ApprovalRequest:
        """Reject a pending request (no side effects on the resource).

        Raises ValueError if the request does not exist or is not pending.
        """
        req = self._get_pending(approval_id)
        req.status = "rejected"
        req.reviewed_by = reviewed_by
        req.review_note = note
        req.reviewed_at = datetime.utcnow()
        self._session.flush()

        logger.info(
            "approval request rejected",
            extra={
                "approval_id": approval_id,
                "action": req.action,
                "resource_id": req.resource_id,
                "reviewed_by": reviewed_by,
            },
        )
        return req

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_pending(self) -> list[ApprovalRequest]:
        from sqlalchemy import select  # noqa: PLC0415

        stmt = select(ApprovalRequest).where(ApprovalRequest.status == "pending")
        return list(self._session.execute(stmt).scalars())

    def list_all(self) -> list[ApprovalRequest]:
        from sqlalchemy import select  # noqa: PLC0415

        stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def get_by_id(self, approval_id: str) -> ApprovalRequest | None:
        return self._session.get(ApprovalRequest, approval_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_pending(self, approval_id: str) -> ApprovalRequest:
        req = self._session.get(ApprovalRequest, approval_id)
        if req is None:
            raise ValueError(f"Approval request not found: {approval_id}")
        if req.status != "pending":
            raise ValueError(f"Approval request {approval_id} is already {req.status}")
        return req

    def _execute_approved(self, req: ApprovalRequest) -> None:
        if req.action == "delete_document":
            doc = self._session.get(DocumentRecord, req.resource_id)
            if doc:
                doc.status = "deleted"
                self._session.flush()
