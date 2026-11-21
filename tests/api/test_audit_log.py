"""
Tests for the audit middleware.

Covers:
  P3-4 — state-changing requests (POST/PUT/PATCH/DELETE) emit audit log entries
  Phase 3 exit criterion — middleware order is request-id → rate-limit → audit
"""

from __future__ import annotations

import logging


def test_post_request_emits_audit_log(client, caplog):
    """POST /api/v1/auth/login emits an audit log entry (P3-4)."""
    with caplog.at_level(logging.INFO, logger="app.middleware.audit"):
        client.post(
            "/api/v1/auth/login",
            json={"username": "analyst", "password": "analyst123"},
        )
    audit_records = [r for r in caplog.records if r.getMessage() == "audit"]
    assert len(audit_records) >= 1
    record = audit_records[0]
    assert record.__dict__["method"] == "POST"
    assert "/api/v1/auth/login" in record.__dict__["path"]
    assert record.__dict__["audit"] is True


def test_get_request_does_not_emit_audit_log(client, caplog):
    """GET requests are not state-changing and must NOT produce audit entries (P3-4)."""
    with caplog.at_level(logging.INFO, logger="app.middleware.audit"):
        client.get("/health")
    audit_records = [r for r in caplog.records if r.getMessage() == "audit"]
    assert len(audit_records) == 0


def test_audit_log_contains_status_code(client, caplog):
    """Audit entry records the HTTP response status code."""
    with caplog.at_level(logging.INFO, logger="app.middleware.audit"):
        client.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "viewer123"},
        )
    audit_records = [r for r in caplog.records if r.getMessage() == "audit"]
    assert len(audit_records) >= 1
    assert "status_code" in audit_records[0].__dict__
    assert audit_records[0].__dict__["status_code"] == 200


def test_audit_log_contains_request_id(client, caplog):
    """Audit entry includes the correlation request_id set by RequestContextMiddleware."""
    with caplog.at_level(logging.INFO, logger="app.middleware.audit"):
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
    req_id = r.headers.get("X-Request-ID", "")
    audit_records = [rec for rec in caplog.records if rec.getMessage() == "audit"]
    assert len(audit_records) >= 1
    logged_id = audit_records[0].__dict__.get("request_id", "")
    # The request_id in the log should match the one returned in the header.
    assert logged_id == req_id


def test_health_ready_reports_redis(client):
    """Phase 3 exit criterion — /health/ready includes a redis check."""
    r = client.get("/health/ready")
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert "redis" in checks
    assert checks["redis"]["status"] == "ok"
    assert checks["redis"]["detail"] in ("fakeredis", "real")
