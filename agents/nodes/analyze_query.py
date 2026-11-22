"""Node: analyze_query — extract intent, entities, time range (F2)."""

from __future__ import annotations

from agents.rules import analyze_question
from agents.state import ResearchState


def analyze_query(state: ResearchState) -> ResearchState:
    analysis = analyze_question(state["question"])
    return {
        **state,
        "intent": analysis["intent"],
        "entities": analysis["entities"],
        "time_range": analysis["time_range"],
        "needs_relationships": analysis["needs_relationships"],
        "needs_aggregation": analysis["needs_aggregation"],
    }
