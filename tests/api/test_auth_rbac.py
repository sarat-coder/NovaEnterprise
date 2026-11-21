"""
Tests for JWT authentication and role-based access control.

Covers:
  P3-1 — JWT creation, decode, role hierarchy
  P3-2 — Demo login endpoint
  Phase 3 exit criterion — no token → 401, viewer on analyst route → 403
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _login(client, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _auth_headers(client, username: str, password: str) -> dict:
    r = _login(client, username, password)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------


def test_login_viewer_returns_200_with_token(client):
    """POST /api/v1/auth/login with valid viewer credentials → 200 with JWT (P3-2)."""
    r = _login(client, "viewer", "viewer123")
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "viewer"


def test_login_analyst_returns_analyst_role(client):
    """Login as analyst → JWT with role=analyst."""
    r = _login(client, "analyst", "analyst123")
    assert r.status_code == 200
    assert r.json()["role"] == "analyst"


def test_login_admin_returns_admin_role(client):
    """Login as admin → JWT with role=admin."""
    r = _login(client, "admin", "admin123")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_login_wrong_password_returns_401(client):
    """Wrong password → 401 Unauthorized (N8-adjacent: no credentials in error body)."""
    r = _login(client, "analyst", "wrongpass")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_login_unknown_user_returns_401(client):
    """Unknown username → 401."""
    r = _login(client, "nobody", "password")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /me — requires any authenticated role
# ---------------------------------------------------------------------------


def test_me_no_token_returns_401(client):
    """GET /api/v1/auth/me with no token → 401 (Phase 3 exit criterion)."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_invalid_token_returns_401(client):
    """GET /api/v1/auth/me with a malformed token → 401."""
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer notavalidtoken"})
    assert r.status_code == 401


def test_me_viewer_token_returns_200(client):
    """Viewer token is enough to call /me."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["sub"] == "viewer"
    assert body["role"] == "viewer"


def test_me_analyst_token_returns_200(client):
    """Analyst token is also valid on /me."""
    headers = _auth_headers(client, "analyst", "analyst123")
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "analyst"


# ---------------------------------------------------------------------------
# Analyst-only route — proves viewer < analyst < admin role ordering
# ---------------------------------------------------------------------------


def test_analyst_only_no_token_returns_401(client):
    """No token → 401 on analyst-only route."""
    r = client.get("/api/v1/auth/analyst-only")
    assert r.status_code == 401


def test_analyst_only_viewer_returns_403(client):
    """Viewer token → 403 on analyst-only route (Phase 3 exit criterion)."""
    headers = _auth_headers(client, "viewer", "viewer123")
    r = client.get("/api/v1/auth/analyst-only", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "Insufficient permissions"


def test_analyst_only_analyst_returns_200(client):
    """Analyst token → 200 on analyst-only route."""
    headers = _auth_headers(client, "analyst", "analyst123")
    r = client.get("/api/v1/auth/analyst-only", headers=headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_analyst_only_admin_returns_200(client):
    """Admin role satisfies the analyst-minimum requirement (admin > analyst)."""
    headers = _auth_headers(client, "admin", "admin123")
    r = client.get("/api/v1/auth/analyst-only", headers=headers)
    assert r.status_code == 200
