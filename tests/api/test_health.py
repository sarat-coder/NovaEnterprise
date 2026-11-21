"""
Tests for the health endpoints.

Covers:
  N5 — every response carries X-Request-ID
  Phase 1 exit criterion — /health and /health/live return 200
  Phase 1 exit criterion — /health/ready returns {status, checks}
"""

from __future__ import annotations


def test_health_returns_200(client):
    """GET /health → 200 {"status": "ok"}"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_live_returns_200(client):
    """GET /health/live → 200 {"status": "ok"}"""
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_ready_returns_check_registry(client):
    """GET /health/ready → 200, body has status and checks keys (Phase 1 exit criterion)."""
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "checks" in body
    assert isinstance(body["checks"], dict)


def test_health_ready_app_check_present(client):
    """The 'app' check is registered at startup and reports ok."""
    r = client.get("/health/ready")
    checks = r.json()["checks"]
    assert "app" in checks
    assert checks["app"]["status"] == "ok"
    assert checks["app"]["detail"] == "fastapi"
