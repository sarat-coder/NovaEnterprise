"""Documents API — upload, browse, and delete (P9-4, P9-5).

F13: ingest (via upload)
F17: admin-gated delete via approval service

Endpoints:
  GET    /api/v1/documents            viewer+   list all documents
  POST   /api/v1/documents/upload     analyst+  upload & ingest a file
  GET    /api/v1/documents/{id}       viewer+   get a document record
  DELETE /api/v1/documents/{id}       analyst+  request deletion (creates approval)
  GET    /api/v1/approvals            admin     list approval requests
  POST   /api/v1/approvals/{id}/approve  admin  approve a request
  POST   /api/v1/approvals/{id}/reject   admin  reject a request
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import Role, UserContext, require_role
from app.repositories.document_repo import DocumentRepository
from app.schemas.documents import (
    ApprovalDecisionIn,
    ApprovalRequestOut,
    DocumentBrief,
    DocumentOut,
    DocumentUploadResponse,
)
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/api/v1", tags=["documents"])

# Extension allowlist (N7) — mirrors rag/ingest.py ALLOWED_EXTENSIONS
_ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get("/documents", response_model=list[DocumentBrief])
def list_documents(
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentBrief]:
    repo = DocumentRepository(db)
    docs = [d for d in repo.get_all() if d.status != "deleted"]
    return [DocumentBrief.model_validate(d) for d in docs]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str,
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentOut:
    repo = DocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if doc is None or doc.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
def upload_document(
    user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """Upload and ingest a document.

    Validates:
    - Extension must be .md, .txt, or .pdf (N7)
    - Size must be ≤ MAX_UPLOAD_MB (N7)
    """
    settings = get_settings()

    # Extension check
    from pathlib import Path  # noqa: PLC0415

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type {suffix!r}. Allowed: .md, .txt, .pdf",
        )

    # Size check
    content = file.file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_mb} MB limit",
        )

    # Ingest
    try:
        from rag.ingest import ingest_bytes  # noqa: PLC0415

        doc_id = ingest_bytes(content, file.filename or "upload", db, uploaded_by=user.sub)
        db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingest failed: {exc}",
        ) from exc

    repo = DocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    chunk_count = doc.chunk_count if doc else 0
    flagged = doc.flagged if doc else False

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename or "upload",
        chunk_count=chunk_count,
        flagged=flagged,
        message="Document indexed" + (" (flagged for review)" if flagged else ""),
    )


@router.delete("/documents/{doc_id}", response_model=ApprovalRequestOut, status_code=202)
def request_document_delete(
    doc_id: str,
    user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    """Request deletion of a document.

    Creates an approval request (F17). The document is NOT deleted until
    an admin approves via POST /api/v1/approvals/{id}/approve.
    """
    svc = ApprovalService(db)
    try:
        req = svc.request_document_delete(doc_id, requested_by=user.sub)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApprovalRequestOut.model_validate(req)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


@router.get("/approvals", response_model=list[ApprovalRequestOut])
def list_approvals(
    _user: Annotated[UserContext, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    pending_only: bool = False,
) -> list[ApprovalRequestOut]:
    svc = ApprovalService(db)
    items = svc.list_pending() if pending_only else svc.list_all()
    return [ApprovalRequestOut.model_validate(r) for r in items]


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRequestOut)
def approve_request(
    approval_id: str,
    body: ApprovalDecisionIn,
    user: Annotated[UserContext, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    svc = ApprovalService(db)
    try:
        req = svc.approve(approval_id, reviewed_by=user.sub, note=body.note)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApprovalRequestOut.model_validate(req)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRequestOut)
def reject_request(
    approval_id: str,
    body: ApprovalDecisionIn,
    user: Annotated[UserContext, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestOut:
    svc = ApprovalService(db)
    try:
        req = svc.reject(approval_id, reviewed_by=user.sub, note=body.note)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ApprovalRequestOut.model_validate(req)
