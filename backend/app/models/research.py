from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="running")
    user_id: Mapped[str | None] = mapped_column(String(200))
    complexity: Mapped[str | None] = mapped_column(String(20))
    strategies_used: Mapped[str | None] = mapped_column(Text)  # JSON array stored as text
    answer: Mapped[str | None] = mapped_column(Text)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    corrective_rounds: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), default="transition")
    payload: Mapped[str | None] = mapped_column(Text)  # JSON
    duration_ms: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(80), default="text/markdown")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="indexed")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str | None] = mapped_column(String(200))
    flagged: Mapped[bool] = mapped_column(default=False)
    flag_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(200))
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
