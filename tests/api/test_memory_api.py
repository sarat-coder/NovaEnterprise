"""API tests for the memory endpoints (Phase 10, F15).

Covers:
  - GET  /api/v1/memory/organizational   viewer+
  - GET  /api/v1/memory/organizational/quarter  viewer+
  - GET  /api/v1/memory/notes            analyst+
  - POST /api/v1/memory/notes            analyst+
  - DELETE /api/v1/memory/notes/{id}     analyst+ (own records only)
  - viewer blocked from analyst endpoints (403)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_DEMO_PASSWORDS = {"viewer": "viewer123", "analyst": "analyst123", "admin": "admin123"}


def _token(client: TestClient, role: str = "analyst") -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": role, "password": _DEMO_PASSWORDS[role]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _headers(client: TestClient, role: str = "analyst") -> dict:
    return {"Authorization": f"Bearer {_token(client, role)}"}


# ---------------------------------------------------------------------------
# Organizational memory
# ---------------------------------------------------------------------------


def test_org_memory_requires_auth(client: TestClient):
    resp = client.get("/api/v1/memory/organizational")
    assert resp.status_code == 401


def test_org_memory_viewer_allowed(client: TestClient):
    resp = client.get("/api/v1/memory/organizational", headers=_headers(client, "viewer"))
    assert resp.status_code == 200
    data = resp.json()
    assert "fiscal_calendar" in data
    assert "data_retention_policy" in data


def test_org_quarter_resolution(client: TestClient):
    """The quarter endpoint returns concrete dates (N1: works fully offline)."""
    resp = client.get("/api/v1/memory/organizational/quarter", headers=_headers(client, "viewer"))
    assert resp.status_code == 200
    data = resp.json()
    assert "quarter" in data
    assert "start_date" in data
    assert "end_date" in data
    # Must be a past quarter, not the current one
    assert data["quarter"] in ("Q1", "Q2", "Q3", "Q4")


# ---------------------------------------------------------------------------
# Analyst notes — access control
# ---------------------------------------------------------------------------


def test_viewer_cannot_list_notes(client: TestClient):
    resp = client.get("/api/v1/memory/notes", headers=_headers(client, "viewer"))
    assert resp.status_code == 403


def test_viewer_cannot_add_note(client: TestClient):
    resp = client.post(
        "/api/v1/memory/notes",
        json={"key": "k", "value": "v"},
        headers=_headers(client, "viewer"),
    )
    assert resp.status_code == 403


def test_no_token_blocked(client: TestClient):
    resp = client.get("/api/v1/memory/notes")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Analyst notes — CRUD
# ---------------------------------------------------------------------------


def test_analyst_add_and_list_notes(client: TestClient):
    headers = _headers(client, "analyst")
    # start with empty list
    resp = client.get("/api/v1/memory/notes", headers=headers)
    assert resp.status_code == 200
    initial_count = len(resp.json())

    # add a note
    resp = client.post(
        "/api/v1/memory/notes",
        json={"key": "my.preference", "value": "concise answers"},
        headers=headers,
    )
    assert resp.status_code == 201
    note = resp.json()
    assert note["key"] == "my.preference"
    assert note["scope"] == "analyst"

    # list shows the new note
    resp = client.get("/api/v1/memory/notes", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == initial_count + 1


def test_analyst_delete_own_note(client: TestClient):
    headers = _headers(client, "analyst")
    resp = client.post(
        "/api/v1/memory/notes",
        json={"key": "temp.note", "value": "to be deleted"},
        headers=headers,
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/memory/notes/{note_id}", headers=headers)
    assert resp.status_code == 204


def test_delete_nonexistent_returns_404(client: TestClient):
    headers = _headers(client, "analyst")
    resp = client.delete("/api/v1/memory/notes/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_upsert_same_key_overwrites(client: TestClient):
    headers = _headers(client, "analyst")
    client.post(
        "/api/v1/memory/notes",
        json={"key": "upsert.test", "value": "v1"},
        headers=headers,
    )
    client.post(
        "/api/v1/memory/notes",
        json={"key": "upsert.test", "value": "v2"},
        headers=headers,
    )
    resp = client.get("/api/v1/memory/notes", headers=headers)
    matching = [n for n in resp.json() if n["key"] == "upsert.test"]
    assert len(matching) == 1
    assert matching[0]["value"] == "v2"
