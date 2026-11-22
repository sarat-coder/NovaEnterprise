"""Node: decompose — split into ≤ MAX_SUBQUESTIONS sub-questions (F4)."""

from __future__ import annotations

from agents.rules import correct_routing, decompose_question
from agents.state import ResearchState
from app.core.config import get_settings


def decompose(state: ResearchState) -> ResearchState:
    settings = get_settings()
    analysis = {
        "intent": state.get("intent", ""),
        "entities": state.get("entities", []),
        "time_range": state.get("time_range", {}),
        "needs_relationships": state.get("needs_relationships", False),
        "needs_aggregation": state.get("needs_aggregation", False),
    }
    sub_questions = decompose_question(
        state["question"],
        analysis,
        state.get("complexity", "simple"),
        max_subquestions=settings.max_subquestions,
    )
    sub_questions = correct_routing(sub_questions)
    return {**state, "sub_questions": sub_questions}
