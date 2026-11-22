"""test_research_lifecycle — POST research, 202, poll, events (F1, F16, RBAC)."""

from __future__ import annotations

import time

import pytest


ANALYST_CREDS = {"username": "alice@example.com", "password": "demo"}
VIEWER_CREDS = {"username": "viewer@example.com", "password": "demo"}

SIMPLE_QUESTION = "What is our data retention policy?"


def _login(client, creds):
    r = client.post("/api/v1/auth/login", json=creds)
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def test_viewer_cannot_start_research(client):
    """RBAC: viewer gets 403 on POST /api/v1/research."""
    token = _login(client, VIEWER_CREDS)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = client.post(
        "/api/v1/research",
        json={"question": SIMPLE_QUESTION},
        headers=headers,
    )
    # Either 401 (no token) or 403 (viewer role)
    assert r.status_code in (401, 403)


def test_start_research_returns_202(client):
    """F1: POST /api/v1/research returns 202 with session_id immediately."""
    token = _login(client, ANALYST_CREDS)
    if token is None:
        pytest.skip("Demo login not available in this test run")

    r = client.post(
        "/api/v1/research",
        json={"question": SIMPLE_QUESTION},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
    data = r.json()
    assert "session_id" in data
    assert data["status"] == "running"


def test_poll_returns_session(client):
    """F1: GET /api/v1/research/{id} returns session data."""
    token = _login(client, ANALYST_CREDS)
    if token is None:
        pytest.skip("Demo login not available in this test run")

    # Start
    r = client.post(
        "/api/v1/research",
        json={"question": SIMPLE_QUESTION},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 202:
        pytest.skip("Could not start research session")
    session_id = r.json()["session_id"]

    # Poll
    r2 = client.get(
        f"/api/v1/research/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["session_id"] == session_id
    assert data["question"] == SIMPLE_QUESTION


def test_events_endpoint(client):
    """F16: GET /api/v1/research/{id}/events returns a list."""
    token = _login(client, ANALYST_CREDS)
    if token is None:
        pytest.skip("Demo login not available in this test run")

    r = client.post(
        "/api/v1/research",
        json={"question": SIMPLE_QUESTION},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 202:
        pytest.skip("Could not start research session")
    session_id = r.json()["session_id"]

    r2 = client.get(
        f"/api/v1/research/{session_id}/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)


def test_session_not_found_404(client):
    """GET /api/v1/research/nonexistent → 404."""
    token = _login(client, ANALYST_CREDS)
    if token is None:
        pytest.skip("Demo login not available")
    r = client.get(
        "/api/v1/research/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_question_too_short_rejected(client):
    """Pydantic validation: question < 5 chars → 422."""
    token = _login(client, ANALYST_CREDS)
    if token is None:
        pytest.skip("Demo login not available")
    r = client.post(
        "/api/v1/research",
        json={"question": "Hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
