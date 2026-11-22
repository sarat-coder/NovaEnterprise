"""Pydantic schemas for the documents and approvals API (P9-4, P9-5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    chunk_count: int
    uploaded_by: str | None
    flagged: bool
    flag_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentBrief(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    flagged: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    flagged: bool
    message: str


class ApprovalRequestOut(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str
    requested_by: str
    reason: str | None
    status: str
    reviewed_by: str | None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalDecisionIn(BaseModel):
    note: str = ""
