"""test_graph_shape_matches_frontend_assumptions — guard GRAPH_NODES and GRAPH_EDGES."""

from __future__ import annotations

from agents.graph import GRAPH_EDGES, GRAPH_NODES, build_graph

EXPECTED_NODES = {
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
}


def test_graph_nodes_match_expected():
    """F16 / FRONTEND_ASSUMPTIONS: all expected node ids are present."""
    assert set(GRAPH_NODES) == EXPECTED_NODES


def test_graph_edges_cover_all_nodes():
    """Every node except the entry point appears in at least one edge."""
    edge_targets = {t for _, t in GRAPH_EDGES if t != "__end__"}
    edge_sources = {s for s, _ in GRAPH_EDGES}
    referenced = edge_targets | edge_sources
    # Every expected node should appear in the edge list
    for node in EXPECTED_NODES:
        assert node in referenced, f"Node '{node}' is not referenced in any edge"


def test_graph_compiles():
    """build_graph() returns a compiled runnable without error."""
    compiled = build_graph()
    assert compiled is not None
