"""Node: route_retrieval — apply final routing corrections (F5).

The actual dispatch to strategy-specific nodes happens via GRAPH_EDGES in
agents/graph.py. This node validates and re-applies correct_routing() as a
safety net so the state going into retrieval is always correct.
"""

from __future__ import annotations

from agents.rules import correct_routing
from agents.state import ResearchState


def route_retrieval(state: ResearchState) -> ResearchState:
    sub_questions = correct_routing(state.get("sub_questions", []))
    return {**state, "sub_questions": sub_questions}
