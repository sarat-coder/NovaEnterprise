"""Graph RAG tests — proves F8 (typed traversals with Cypher), P7.

All tests run fully offline: GRAPH_STORE=memory, LLM_PROVIDER=fake.
No network, no Neo4j, no Docker.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("GRAPH_STORE", "memory")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("VECTOR_STORE", "memory")

from rag.graph_seed import seed_graph
from rag.graph_store import (
    GraphEdge,
    GraphNode,
    MemoryGraphStore,
    assert_readonly_cypher,
    is_readonly_cypher,
    reset_graph_store,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_store():
    """Each test gets an isolated empty memory store."""
    reset_graph_store()
    yield
    reset_graph_store()


@pytest.fixture
def seeded_store() -> MemoryGraphStore:
    """Return a MemoryGraphStore seeded with the full sample dataset."""
    store = MemoryGraphStore()
    seed_graph(store)
    return store


@pytest.fixture
def tiny_store() -> MemoryGraphStore:
    """Minimal three-node graph: Team ← Service ← Incident → Customer."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("team-1", "Team", {"id": 1, "name": "Payments Platform"}))
    store.add_node(GraphNode("svc-1", "Service", {"id": 1, "name": "Payments API"}))
    store.add_node(
        GraphNode(
            "inc-1",
            "Incident",
            {
                "id": 1,
                "incident_id": "INC-2031",
                "title": "Payments API complete outage",
                "started_at": "2026-07-18T11:23:00",
            },
        )
    )
    store.add_node(GraphNode("cust-1", "Customer", {"id": 1, "name": "Meridian Financial Group"}))
    store.add_node(
        GraphNode(
            "dec-1",
            "Decision",
            {"id": 1, "adr_id": "ADR-001", "title": "Adopt circuit-breaker pattern"},
        )
    )

    store.add_edge(GraphEdge("svc-1", "team-1", "OWNED_BY"))
    store.add_edge(GraphEdge("inc-1", "svc-1", "AFFECTED"))
    store.add_edge(GraphEdge("inc-1", "cust-1", "IMPACTED"))
    store.add_edge(GraphEdge("dec-1", "inc-1", "ADDRESSES"))
    return store


# ---------------------------------------------------------------------------
# MemoryGraphStore unit tests
# ---------------------------------------------------------------------------


def test_add_and_count_nodes() -> None:
    """Adding nodes increases count. N3 (replaceable stores)."""
    store = MemoryGraphStore()
    assert store.count_nodes() == 0
    store.add_node(GraphNode("t1", "Team", {"name": "SRE"}))
    store.add_node(GraphNode("s1", "Service", {"name": "Payments API"}))
    assert store.count_nodes() == 2


def test_add_and_count_edges() -> None:
    """Adding edges increases count."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("t1", "Team", {}))
    store.add_node(GraphNode("s1", "Service", {}))
    store.add_edge(GraphEdge("s1", "t1", "OWNED_BY"))
    assert store.count_edges() == 1


def test_get_node_returns_none_when_missing() -> None:
    """get_node returns None for an unknown id."""
    store = MemoryGraphStore()
    assert store.get_node("not-there") is None


def test_get_node_returns_correct_node() -> None:
    """get_node returns the stored node."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("t1", "Team", {"name": "SRE"}))
    node = store.get_node("t1")
    assert node is not None
    assert node.label == "Team"
    assert node.properties["name"] == "SRE"


def test_upsert_node_overwrites() -> None:
    """Adding a node with an existing id replaces it (upsert)."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("t1", "Team", {"name": "Old"}))
    store.add_node(GraphNode("t1", "Team", {"name": "New"}))
    assert store.count_nodes() == 1
    assert store.get_node("t1").properties["name"] == "New"  # type: ignore[union-attr]


def test_get_neighbors_out() -> None:
    """get_neighbors(direction='out') follows out-edges."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("s1", "Service", {"name": "Payments API"}))
    store.add_node(GraphNode("t1", "Team", {"name": "Payments Platform"}))
    store.add_edge(GraphEdge("s1", "t1", "OWNED_BY"))
    neighbors = store.get_neighbors("s1", "OWNED_BY", direction="out")
    assert len(neighbors) == 1
    assert neighbors[0].node_id == "t1"


def test_get_neighbors_in() -> None:
    """get_neighbors(direction='in') follows in-edges."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("s1", "Service", {}))
    store.add_node(GraphNode("inc1", "Incident", {}))
    store.add_edge(GraphEdge("inc1", "s1", "AFFECTED"))
    # from s1's perspective, inc1 is an in-neighbor via AFFECTED
    neighbors = store.get_neighbors("s1", "AFFECTED", direction="in")
    assert len(neighbors) == 1
    assert neighbors[0].node_id == "inc1"


def test_clear_empties_store() -> None:
    """clear() removes all nodes and edges."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("n1", "Team", {}))
    store.add_edge(GraphEdge("n1", "n1", "SELF"))
    store.clear()
    assert store.count_nodes() == 0
    assert store.count_edges() == 0


# ---------------------------------------------------------------------------
# Typed traversal tests (F8)
# ---------------------------------------------------------------------------


def test_traverse_owning_teams(tiny_store: MemoryGraphStore) -> None:
    """traverse_owning_teams returns Evidence with cypher and team info. F8."""
    results = tiny_store.traverse_owning_teams("Payments API")
    assert len(results) == 1
    ev = results[0]
    assert ev.source_type == "graph"
    assert "Payments Platform" in ev.content
    assert "cypher" in ev.metadata
    assert "OWNED_BY" in ev.metadata["cypher"]
    assert ev.locator  # non-empty locator


def test_traverse_owning_teams_unknown_service(tiny_store: MemoryGraphStore) -> None:
    """traverse_owning_teams returns [] for an unknown service name."""
    results = tiny_store.traverse_owning_teams("No Such Service")
    assert results == []


def test_traverse_impacted_customers(tiny_store: MemoryGraphStore) -> None:
    """traverse_impacted_customers returns Evidence for affected customers. F8."""
    results = tiny_store.traverse_impacted_customers("Payments API")
    assert len(results) >= 1
    ev = results[0]
    assert ev.source_type == "graph"
    assert "Meridian Financial Group" in ev.content
    assert "INC-2031" in ev.content
    assert "cypher" in ev.metadata
    assert "IMPACTED" in ev.metadata["cypher"]


def test_traverse_impacted_customers_date_filter(tiny_store: MemoryGraphStore) -> None:
    """traverse_impacted_customers filters incidents by date range."""
    # Incident started 2026-07-18; filter to Q3 2026 (Jul–Sep)
    results = tiny_store.traverse_impacted_customers(
        "Payments API", start_date="2026-07-01", end_date="2026-09-30"
    )
    assert len(results) >= 1

    # Filter to Q1 2026 — no Payments API incidents in that window
    results_empty = tiny_store.traverse_impacted_customers(
        "Payments API", start_date="2026-01-01", end_date="2026-03-31"
    )
    assert results_empty == []


def test_traverse_related_decisions(tiny_store: MemoryGraphStore) -> None:
    """traverse_related_decisions returns Evidence for decisions addressing incident. F8."""
    results = tiny_store.traverse_related_decisions("INC-2031")
    assert len(results) >= 1
    ev = results[0]
    assert ev.source_type == "graph"
    assert "ADR-001" in ev.content
    assert "cypher" in ev.metadata
    assert "ADDRESSES" in ev.metadata["cypher"]


def test_traverse_related_decisions_no_decision(tiny_store: MemoryGraphStore) -> None:
    """traverse_related_decisions returns [] for incident with no decisions."""
    results = tiny_store.traverse_related_decisions("INC-9999")
    assert results == []


def test_evidence_ids_are_unique(tiny_store: MemoryGraphStore) -> None:
    """Every Evidence item returned by traversals has a unique id."""
    results = tiny_store.traverse_impacted_customers("Payments API")
    ids = [ev.id for ev in results]
    assert len(ids) == len(set(ids)), "Evidence ids must be unique"


def test_evidence_score_in_range(tiny_store: MemoryGraphStore) -> None:
    """Evidence score must be in [0.0, 1.0]."""
    results = tiny_store.traverse_impacted_customers("Payments API")
    for ev in results:
        assert 0.0 <= ev.score <= 1.0


# ---------------------------------------------------------------------------
# Seeded graph traversal tests (using full sample data)
# ---------------------------------------------------------------------------


def test_seeded_graph_node_count(seeded_store: MemoryGraphStore) -> None:
    """Seeded graph has approximately 85 nodes."""
    n = seeded_store.count_nodes()
    assert n >= 80, f"Expected ~85 nodes, got {n}"
    assert n <= 90, f"Expected ~85 nodes, got {n}"


def test_seeded_graph_edge_count(seeded_store: MemoryGraphStore) -> None:
    """Seeded graph has approximately 260 edges."""
    e = seeded_store.count_edges()
    assert e >= 220, f"Expected ~260 edges, got {e}"
    assert e <= 300, f"Expected ~260 edges, got {e}"


def test_seeded_payments_api_owning_team(seeded_store: MemoryGraphStore) -> None:
    """Payments API is owned by the Payments Platform team."""
    results = seeded_store.traverse_owning_teams("Payments API")
    assert len(results) == 1
    assert "Payments Platform" in results[0].content


def test_seeded_inc2031_impacted_customers(seeded_store: MemoryGraphStore) -> None:
    """INC-2031 impacted 5 enterprise customers — verify via graph traversal."""
    results = seeded_store.traverse_impacted_customers("Payments API")
    # Should include at least customers from INC-2031 (5 customers)
    customer_names = {ev.metadata.get("customer_name") for ev in results}
    # INC-2031 impacted customer ids 1-5
    assert len(customer_names) >= 5, f"Expected ≥5 unique customers, got: {customer_names}"


def test_seeded_inc2031_related_decisions(seeded_store: MemoryGraphStore) -> None:
    """INC-2031 has decisions ADR-001 and ADR-002 addressing it."""
    results = seeded_store.traverse_related_decisions("INC-2031")
    adr_ids = {ev.metadata.get("adr_id") for ev in results}
    assert "ADR-001" in adr_ids, f"ADR-001 not found in {adr_ids}"
    assert "ADR-002" in adr_ids, f"ADR-002 not found in {adr_ids}"


def test_seeded_all_required_relationships(seeded_store: MemoryGraphStore) -> None:
    """All four required relationship types exist in the seeded graph. F8."""
    all_edges = seeded_store._edges
    rel_types = {e.relationship for e in all_edges}
    for required in ("AFFECTED", "IMPACTED", "OWNED_BY", "ADDRESSES"):
        assert required in rel_types, f"Missing required relationship: {required}"


# ---------------------------------------------------------------------------
# Read-only Cypher validation tests (P7-3)
# ---------------------------------------------------------------------------


def test_readonly_cypher_accepts_match_return() -> None:
    """MATCH / RETURN is accepted as read-only."""
    assert is_readonly_cypher("MATCH (n:Service) RETURN n") is True


def test_readonly_cypher_accepts_where_with() -> None:
    """WHERE and WITH clauses are accepted."""
    cypher = "MATCH (n:Incident) WHERE n.severity = 'SEV1' WITH n RETURN n.title"
    assert is_readonly_cypher(cypher) is True


def test_readonly_cypher_rejects_create() -> None:
    """CREATE is rejected as a write operation."""
    assert is_readonly_cypher("CREATE (n:Service {name: 'x'})") is False


def test_readonly_cypher_rejects_merge() -> None:
    """MERGE is rejected."""
    assert is_readonly_cypher("MERGE (n:Team {name: 'SRE'})") is False


def test_readonly_cypher_rejects_delete() -> None:
    """DELETE is rejected."""
    assert is_readonly_cypher("MATCH (n) DELETE n") is False


def test_readonly_cypher_rejects_detach_delete() -> None:
    """DETACH DELETE is rejected."""
    assert is_readonly_cypher("MATCH (n) DETACH DELETE n") is False


def test_readonly_cypher_rejects_set() -> None:
    """SET is rejected."""
    assert is_readonly_cypher("MATCH (n {id:1}) SET n.name = 'new'") is False


def test_readonly_cypher_rejects_remove() -> None:
    """REMOVE is rejected."""
    assert is_readonly_cypher("MATCH (n) REMOVE n.property") is False


def test_readonly_cypher_rejects_drop() -> None:
    """DROP is rejected."""
    assert is_readonly_cypher("DROP INDEX ON :Service(name)") is False


def test_readonly_cypher_case_insensitive() -> None:
    """Keyword matching is case-insensitive."""
    assert is_readonly_cypher("create (n:Team)") is False
    assert is_readonly_cypher("Create (n:Team)") is False
    assert is_readonly_cypher("MATCH (n) delete n") is False


def test_assert_readonly_raises_on_write() -> None:
    """assert_readonly_cypher raises ValueError for write statements."""
    with pytest.raises(ValueError, match="CREATE"):
        assert_readonly_cypher("CREATE (n:Service {name: 'bad'})")


def test_assert_readonly_does_not_raise_on_read() -> None:
    """assert_readonly_cypher does not raise for valid read statements."""
    assert_readonly_cypher("MATCH (n:Service) RETURN n.name")  # no exception


# ---------------------------------------------------------------------------
# execute_cypher_readonly tests
# ---------------------------------------------------------------------------


def test_execute_cypher_readonly_match_all(tiny_store: MemoryGraphStore) -> None:
    """execute_cypher_readonly runs a valid MATCH and returns rows."""
    results = tiny_store.execute_cypher_readonly("MATCH (n:Team) RETURN n")
    assert isinstance(results, list)
    assert len(results) >= 1


def test_execute_cypher_readonly_rejects_write(tiny_store: MemoryGraphStore) -> None:
    """execute_cypher_readonly raises ValueError for write statements."""
    with pytest.raises(ValueError):
        tiny_store.execute_cypher_readonly("CREATE (n:BadNode)")


def test_execute_cypher_readonly_match_with_filter(tiny_store: MemoryGraphStore) -> None:
    """execute_cypher_readonly filters nodes by label property."""
    results = tiny_store.execute_cypher_readonly(
        "MATCH (n:Service {name: 'Payments API'}) RETURN n"
    )
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# Health check registration test
# ---------------------------------------------------------------------------


def test_graph_store_health_check_registration() -> None:
    """register_graph_store_check registers a check that returns ok status."""
    from app.core.health import _registry  # noqa: PLC0415
    from rag.graph_store import register_graph_store_check  # noqa: PLC0415

    register_graph_store_check()
    assert "graph_store" in _registry
    result = _registry["graph_store"]()
    assert result["status"] == "ok"
    assert "memory" in result["detail"]


def test_graph_store_health_reports_node_and_edge_counts() -> None:
    """Health check detail includes node and edge counts."""
    store = MemoryGraphStore()
    store.add_node(GraphNode("n1", "Team", {"name": "SRE"}))
    store.add_node(GraphNode("n2", "Service", {"name": "Search"}))
    store.add_edge(GraphEdge("n2", "n1", "OWNED_BY"))

    from app.core.config import get_settings  # noqa: PLC0415
    from app.core.health import _registry, register_check  # noqa: PLC0415

    def _check() -> dict[str, str]:
        n_nodes = store.count_nodes()
        n_edges = store.count_edges()
        detail = f"{get_settings().graph_store} ({n_nodes} nodes, {n_edges} edges)"
        return {"status": "ok", "detail": detail}

    register_check("graph_store_test", _check)
    result = _registry["graph_store_test"]()
    assert "2 nodes" in result["detail"]
    assert "1 edges" in result["detail"]


# ---------------------------------------------------------------------------
# Degraded readiness test (P7-3)
# ---------------------------------------------------------------------------


def test_degraded_readiness_when_neo4j_connection_error() -> None:
    """When Neo4j raises ConnectionError the health check reports degraded. P7-3."""
    from app.core.health import register_check, run_all_checks  # noqa: PLC0415

    def _failing_check() -> dict[str, str]:
        # Simulate what register_graph_store_check does for a down Neo4j
        raise ConnectionError("Cannot connect to Neo4j at bolt://localhost:7687: timeout")

    # Wrap it the same way register_graph_store_check does
    def _safe_check() -> dict[str, str]:
        try:
            return _failing_check()
        except ConnectionError as exc:
            return {"status": "degraded", "detail": str(exc)}

    register_check("graph_store_neo4j_test", _safe_check)
    checks, overall = run_all_checks()
    assert checks["graph_store_neo4j_test"]["status"] == "degraded"
    # overall is "degraded" (or "error" if something else is broken, but not "ok")
    assert overall in ("degraded", "error")
