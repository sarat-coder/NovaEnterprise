from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Evidence

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The research question (5–2000 characters)",
    )


# ---------------------------------------------------------------------------
# Sub-question
# ---------------------------------------------------------------------------


class SubQuestion(BaseModel):
    id: str
    question: str
    strategy: str  # vector | sql | graph | hybrid
    status: str = "pending"  # pending | running | completed | error
    evidence_ids: list[str] = []
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# Session response shapes
# ---------------------------------------------------------------------------


class ResearchStarted(BaseModel):
    session_id: str
    status: str = "running"


class ResearchSessionOut(BaseModel):
    session_id: str
    question: str
    status: str  # running | completed | error
    complexity: str | None = None  # simple | moderate | complex
    strategies_used: list[str] = []
    sub_questions: list[SubQuestion] = []
    evidence: list[Evidence] = []
    answer: str | None = None
    citations_valid: bool | None = None
    evidence_count: int = 0
    citation_count: int = 0
    corrective_rounds: int = 0
    memory_scopes: dict[str, Any] = Field(
        default_factory=lambda: {
            "organizational": {},
            "conversation": {},
            "session": {},
            "user": {},
        }
    )
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Workflow events
# ---------------------------------------------------------------------------


class WorkflowEventOut(BaseModel):
    id: int
    node: str
    event_type: str
    payload: dict[str, Any] = {}
    duration_ms: float | None = None
    occurred_at: datetime

    model_config = {"from_attributes": True}
