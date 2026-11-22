"""LangGraph workflow wiring (P12-2, §6.1).

GRAPH_NODES and GRAPH_EDGES are the contract the frontend renders.
test_graph_shape_matches_frontend_assumptions guards this list.

13 visible nodes (the 4 retrieval nodes count as one conceptual step but are
separate LangGraph nodes; collect_evidence is re-entered after corrective_retrieval):
  analyze_query → assess_complexity → decompose → route_retrieval
  → vector_retrieval | sql_retrieval | graph_retrieval | hybrid_retrieval
  → collect_evidence → check_missing_evidence
    └─ corrective_retrieval → collect_evidence (loop, bounded)
  → verify_evidence → synthesize_answer → verify_citations
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.check_missing_evidence import check_missing_evidence
from agents.nodes.collect_evidence import collect_evidence
from agents.nodes.corrective_retrieval import corrective_retrieval
from agents.nodes.decompose import decompose
from agents.nodes.graph_retrieval import graph_retrieval
from agents.nodes.hybrid_retrieval import hybrid_retrieval
from agents.nodes.route_retrieval import route_retrieval
from agents.nodes.sql_retrieval import sql_retrieval
from agents.nodes.synthesize_answer import synthesize_answer
from agents.nodes.vector_retrieval import vector_retrieval
from agents.nodes.verify_citations import verify_citations
from agents.nodes.verify_evidence import verify_evidence
from agents.rules import should_correct
from agents.state import ResearchState
from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Node name registry — this is the contract with the frontend
# ---------------------------------------------------------------------------

GRAPH_NODES: list[str] = [
    "analyze_query",
    "assess_complexity",
    "decompose",
    "route_retrieval",
    "vector_retrieval",
    "sql_retrieval",
    "graph_retrieval",
    "hybrid_retrieval",
    "collect_evidence",
    "check_missing_evidence",
    "corrective_retrieval",
    "verify_evidence",
    "synthesize_answer",
    "verify_citations",
]

GRAPH_EDGES: list[tuple[str, str]] = [
    ("analyze_query", "assess_complexity"),
    ("assess_complexity", "decompose"),
    ("decompose", "route_retrieval"),
    ("route_retrieval", "vector_retrieval"),
    ("route_retrieval", "sql_retrieval"),
    ("route_retrieval", "graph_retrieval"),
    ("route_retrieval", "hybrid_retrieval"),
    ("vector_retrieval", "collect_evidence"),
    ("sql_retrieval", "collect_evidence"),
    ("graph_retrieval", "collect_evidence"),
    ("hybrid_retrieval", "collect_evidence"),
    ("collect_evidence", "check_missing_evidence"),
    ("check_missing_evidence", "corrective_retrieval"),  # conditional
    ("check_missing_evidence", "verify_evidence"),  # conditional
    ("corrective_retrieval", "collect_evidence"),
    ("verify_evidence", "synthesize_answer"),
    ("synthesize_answer", "verify_citations"),
    ("verify_citations", END),
]


# ---------------------------------------------------------------------------
# Conditional edge: should we do corrective retrieval or proceed?
# ---------------------------------------------------------------------------


def _should_correct_or_proceed(state: ResearchState) -> str:
    settings = get_settings()
    missing = state.get("missing_evidence_keys", [])
    rounds = state.get("corrective_rounds", 0)
    if should_correct(missing, rounds, settings.max_corrective_rounds):
        return "corrective_retrieval"
    return "verify_evidence"


# ---------------------------------------------------------------------------
# build_graph — called once at startup, cached by the research service
# ---------------------------------------------------------------------------


def build_graph(
    tracer: Any | None = None,
) -> Any:
    """Build and compile the research StateGraph.

    tracer: optional WorkflowTracer — if provided, every node is wrapped.
    """

    def wrap(name: str, fn: Callable) -> Callable:
        if tracer is not None:
            return tracer.node(name)(fn)
        return fn

    graph = StateGraph(ResearchState)  # type: ignore[arg-type]

    graph.add_node("analyze_query", wrap("analyze_query", analyze_query))
    graph.add_node("assess_complexity", wrap("assess_complexity", assess_complexity))
    graph.add_node("decompose", wrap("decompose", decompose))
    graph.add_node("route_retrieval", wrap("route_retrieval", route_retrieval))
    graph.add_node("vector_retrieval", wrap("vector_retrieval", vector_retrieval))
    graph.add_node("sql_retrieval", wrap("sql_retrieval", sql_retrieval))
    graph.add_node("graph_retrieval", wrap("graph_retrieval", graph_retrieval))
    graph.add_node("hybrid_retrieval", wrap("hybrid_retrieval", hybrid_retrieval))
    graph.add_node("collect_evidence", wrap("collect_evidence", collect_evidence))
    graph.add_node(
        "check_missing_evidence",
        wrap("check_missing_evidence", check_missing_evidence),
    )
    graph.add_node(
        "corrective_retrieval",
        wrap("corrective_retrieval", corrective_retrieval),
    )
    graph.add_node("verify_evidence", wrap("verify_evidence", verify_evidence))
    graph.add_node("synthesize_answer", wrap("synthesize_answer", synthesize_answer))
    graph.add_node("verify_citations", wrap("verify_citations", verify_citations))

    graph.set_entry_point("analyze_query")

    graph.add_edge("analyze_query", "assess_complexity")
    graph.add_edge("assess_complexity", "decompose")
    graph.add_edge("decompose", "route_retrieval")

    # All four retrieval nodes run in sequence (LangGraph executes nodes in order
    # for a simple StateGraph without parallelism; each only acts on its own strategy)
    graph.add_edge("route_retrieval", "vector_retrieval")
    graph.add_edge("vector_retrieval", "sql_retrieval")
    graph.add_edge("sql_retrieval", "graph_retrieval")
    graph.add_edge("graph_retrieval", "hybrid_retrieval")
    graph.add_edge("hybrid_retrieval", "collect_evidence")

    graph.add_edge("collect_evidence", "check_missing_evidence")

    graph.add_conditional_edges(
        "check_missing_evidence",
        _should_correct_or_proceed,
        {
            "corrective_retrieval": "corrective_retrieval",
            "verify_evidence": "verify_evidence",
        },
    )

    graph.add_edge("corrective_retrieval", "collect_evidence")
    graph.add_edge("verify_evidence", "synthesize_answer")
    graph.add_edge("synthesize_answer", "verify_citations")
    graph.add_edge("verify_citations", END)

    return graph.compile()
