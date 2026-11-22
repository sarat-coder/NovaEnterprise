"""Tests for the knowledge graph API (P9-6, F14).

Verifies:
- GET  /api/v1/graph/stats           viewer+ gets node/edge counts
- GET  /api/v1/graph/nodes           viewer+ can list nodes
- GET  /api/v1/graph/nodes?label=X   viewer+ can filter by label
- GET  /api/v1/graph/nodes/{id}      viewer+ retrieves a specific node
- GET  /api/v1/graph/nodes/{id}/neighbors  viewer+ expands a node
- POST /api/v1/graph/cypher          analyst+ runs read-only Cypher
- POST /api/v1/graph/cypher          viewer cannot run Cypher (403)
- POST /api/v1/graph/cypher          write Cypher → 422
"""

from __future__ import annotations

import pytest

from rag.graph_seed import seed_graph
from rag.graph_store import get_graph_store, reset_graph_store


def _auth_headers(client, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
def seeded_graph():
    """Ensure the in-memory graph store has data before each test."""
    reset_graph_store()
    store = get_graph_store()
    seed_graph(store)
    yield
    reset_graph_store()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_graph_stats_viewer(client):
    """Viewer can get graph stats (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/graph/stats", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "node_count" in body
    assert "edge_count" in body
    assert body["node_count"] > 0
    assert body["edge_count"] > 0


def test_graph_stats_no_auth_returns_401(client):
    r = client.get("/api/v1/graph/stats")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# List nodes
# ---------------------------------------------------------------------------


def test_list_nodes_viewer_returns_200(client):
    """Viewer can list graph nodes (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/graph/nodes", headers=headers)
    assert r.status_code == 200
    nodes = r.json()
    assert isinstance(nodes, list)
    assert len(nodes) > 0
    first = nodes[0]
    assert "node_id" in first
    assert "label" in first
    assert "properties" in first


def test_list_nodes_filter_by_label(client):
    """Label filter returns only nodes of that type (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/graph/nodes?label=Service", headers=headers)
    assert r.status_code == 200
    nodes = r.json()
    assert all(n["label"] == "Service" for n in nodes)
    assert len(nodes) > 0


def test_list_nodes_no_auth_returns_401(client):
    r = client.get("/api/v1/graph/nodes")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Get node
# ---------------------------------------------------------------------------


def test_get_node_viewer_returns_200(client):
    """Viewer can retrieve a specific node (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    # First, get a valid node id
    r_list = client.get("/api/v1/graph/nodes?label=Service&limit=1", headers=headers)
    assert r_list.status_code == 200
    nodes = r_list.json()
    assert len(nodes) >= 1
    node_id = nodes[0]["node_id"]

    r = client.get(f"/api/v1/graph/nodes/{node_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["node_id"] == node_id


def test_get_nonexistent_node_returns_404(client):
    """Non-existent node_id → 404."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/graph/nodes/does-not-exist", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Expand node (neighbors)
# ---------------------------------------------------------------------------


def test_expand_node_viewer_returns_200(client):
    """Viewer can expand a node and get its neighbours (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r_list = client.get("/api/v1/graph/nodes?label=Service&limit=1", headers=headers)
    node_id = r_list.json()[0]["node_id"]

    r = client.get(f"/api/v1/graph/nodes/{node_id}/neighbors", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "node" in body
    assert "neighbors" in body
    assert "edges" in body
    assert body["node"]["node_id"] == node_id


def test_expand_node_direction_in(client):
    """Expanding with direction=in works (F14)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r_list = client.get("/api/v1/graph/nodes?label=Service&limit=1", headers=headers)
    node_id = r_list.json()[0]["node_id"]

    r = client.get(f"/api/v1/graph/nodes/{node_id}/neighbors?direction=in", headers=headers)
    assert r.status_code == 200


def test_expand_nonexistent_node_returns_404(client):
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/graph/nodes/no-such-node/neighbors", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Read-only Cypher (analyst+)
# ---------------------------------------------------------------------------


def test_cypher_viewer_returns_403(client):
    """Viewer cannot run Cypher (F14 — analyst only)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.post(
        "/api/v1/graph/cypher",
        headers=headers,
        json={"cypher": "MATCH (n:Service) RETURN n"},
    )
    assert r.status_code == 403


def test_cypher_analyst_match_returns_200(client):
    """Analyst can run a valid read-only MATCH query (F14)."""
    headers = _auth_headers(client, "analyst", "analyst123")
    r = client.post(
        "/api/v1/graph/cypher",
        headers=headers,
        json={"cypher": "MATCH (n:Service) RETURN n"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert "row_count" in body
    assert body["row_count"] == len(body["rows"])


def test_cypher_write_clause_returns_422(client):
    """Write Cypher → 422 (F8, read-only guard)."""
    headers = _auth_headers(client, "analyst", "analyst123")
    r = client.post(
        "/api/v1/graph/cypher",
        headers=headers,
        json={"cypher": "CREATE (n:Hack {evil: true}) RETURN n"},
    )
    assert r.status_code == 422
    assert "Write operation" in r.json()["detail"]


def test_cypher_no_auth_returns_401(client):
    r = client.post(
        "/api/v1/graph/cypher",
        json={"cypher": "MATCH (n) RETURN n"},
    )
    assert r.status_code == 401
