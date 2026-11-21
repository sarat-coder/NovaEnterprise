"""
Tests for browse API endpoints: customers, incidents, decisions.

Covers:
  P5-2 — list and detail endpoints for all three resources
  Phase 5 exit criteria — seeded data returned; any role can browse; 404 on missing ids
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


def test_list_customers_viewer_200(client):
    """GET /api/v1/customers — viewer can list customers (Phase 5 exit criterion)."""
    headers = _login(client, "viewer", "viewer123")
    r = client.get("/api/v1/customers", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 10, f"Expected 10 customers from seed, got {len(body)}"
    sample = body[0]
    assert "id" in sample
    assert "name" in sample
    assert "slug" in sample
    assert "segment" in sample


def test_list_customers_no_token_401(client):
    """GET /api/v1/customers — no token → 401."""
    r = client.get("/api/v1/customers")
    assert r.status_code == 401


def test_get_customer_by_id_200(client):
    """GET /api/v1/customers/1 — returns a single customer."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/customers/1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert "name" in body


def test_get_customer_not_found_404(client):
    """GET /api/v1/customers/9999 → 404."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/customers/9999", headers=headers)
    assert r.status_code == 404
    assert "detail" in r.json()


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


def test_list_incidents_viewer_200(client):
    """GET /api/v1/incidents — viewer can list incidents; demo checkpoint: 12 returned."""
    headers = _login(client, "viewer", "viewer123")
    r = client.get("/api/v1/incidents", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 12, f"Expected 12 incidents from seed, got {len(body)}"
    sample = body[0]
    assert "incident_id" in sample
    assert "severity" in sample
    assert "status" in sample


def test_list_incidents_no_token_401(client):
    """GET /api/v1/incidents — no token → 401."""
    r = client.get("/api/v1/incidents")
    assert r.status_code == 401


def test_list_incidents_filter_severity(client):
    """GET /api/v1/incidents?severity=SEV1 — only SEV1 incidents returned."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/incidents?severity=SEV1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert all(inc["severity"] == "SEV1" for inc in body)


def test_get_incident_detail_200(client):
    """GET /api/v1/incidents/1 — returns detail with impacted_customers and decisions."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/incidents/1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "impacted_customers" in body
    assert "decisions" in body
    assert isinstance(body["impacted_customers"], list)
    assert isinstance(body["decisions"], list)


def test_get_incident_not_found_404(client):
    """GET /api/v1/incidents/9999 → 404."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/incidents/9999", headers=headers)
    assert r.status_code == 404
    assert "detail" in r.json()


def test_admin_can_list_incidents(client):
    """Admin can browse incidents too (all roles allowed)."""
    headers = _login(client, "admin", "admin123")
    r = client.get("/api/v1/incidents", headers=headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def test_list_decisions_viewer_200(client):
    """GET /api/v1/decisions — viewer can list decisions; 8 expected from seed."""
    headers = _login(client, "viewer", "viewer123")
    r = client.get("/api/v1/decisions", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 8, f"Expected 8 decisions from seed, got {len(body)}"
    sample = body[0]
    assert "adr_id" in sample
    assert "title" in sample
    assert "status" in sample


def test_list_decisions_no_token_401(client):
    """GET /api/v1/decisions — no token → 401."""
    r = client.get("/api/v1/decisions")
    assert r.status_code == 401


def test_get_decision_detail_200(client):
    """GET /api/v1/decisions/1 — returns detail with incidents list."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/decisions/1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "incidents" in body
    assert isinstance(body["incidents"], list)


def test_get_decision_not_found_404(client):
    """GET /api/v1/decisions/9999 → 404."""
    headers = _login(client, "analyst", "analyst123")
    r = client.get("/api/v1/decisions/9999", headers=headers)
    assert r.status_code == 404
    assert "detail" in r.json()
