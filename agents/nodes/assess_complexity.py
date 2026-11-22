"""Node: assess_complexity — classify simple | moderate | complex (F3)."""

from __future__ import annotations

from agents.rules import classify_complexity
from agents.state import ResearchState


def assess_complexity(state: ResearchState) -> ResearchState:
    analysis = {
        "intent": state.get("intent", ""),
        "entities": state.get("entities", []),
        "time_range": state.get("time_range", {}),
        "needs_relationships": state.get("needs_relationships", False),
        "needs_aggregation": state.get("needs_aggregation", False),
    }
    complexity = classify_complexity(analysis)
    return {**state, "complexity": complexity}
