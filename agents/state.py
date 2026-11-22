"""ResearchState — the shared mutable state threaded through every LangGraph node (P11-1)."""

from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.common import Evidence


class SubQuestionState(TypedDict):
    id: str
    question: str
    strategy: str  # vector | sql | graph | hybrid
    status: str    # pending | running | completed | error
    evidence_ids: list[str]
    error_detail: str | None


class ResearchState(TypedDict):
    # Input
    session_id: str
    question: str

    # Analysis (set by analyze_query)
    intent: str
    entities: list[str]
    time_range: dict[str, str] | None   # {"label": "last_quarter", "relative": "..."}
    needs_relationships: bool
    needs_aggregation: bool

    # Complexity (set by assess_complexity)
    complexity: str   # simple | moderate | complex

    # Decomposition (set by decompose)
    sub_questions: list[SubQuestionState]

    # Retrieval (updated per sub-question)
    evidence: list[Evidence]

    # Corrective loop
    missing_evidence_keys: list[str]
    corrective_rounds: int

    # Synthesis (set by synthesize_answer)
    answer: str | None

    # Citation check (set by verify_citations)
    citations_valid: bool | None

    # Metadata
    strategies_used: list[str]
    error: str | None
