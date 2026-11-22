"""ResearchState — the shared TypedDict that flows through every workflow node.

TypedDict (not Pydantic) because LangGraph's StateGraph expects dict-compatible
state and nodes create updated copies with {**state, "key": new_value}.
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.common import Evidence


class SubQuestionState(TypedDict, total=False):
    id: str
    question: str
    strategy: str  # vector | sql | graph | hybrid
    status: str  # pending | running | completed | error
    evidence_ids: list[str]
    error_detail: str | None


class ResearchState(TypedDict, total=False):
    # Input
    session_id: str
    question: str

    # Analysis (analyze_query)
    intent: str
    entities: list[str]
    time_range: dict[str, Any]
    needs_relationships: bool
    needs_aggregation: bool

    # Complexity + decomposition
    complexity: str  # simple | moderate | complex
    sub_questions: list[SubQuestionState]

    # Retrieval
    evidence: list[Evidence]

    # Corrective loop
    missing_evidence_keys: list[str]
    corrective_rounds: int

    # Answer synthesis
    answer: str
    citations_valid: bool
    strategies_used: list[str]

    # Error passthrough
    error: str | None
