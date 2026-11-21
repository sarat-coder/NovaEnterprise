"""
Tests for the X-Request-ID middleware.

Covers N5 — every response carries X-Request-ID (echoed when sent, generated otherwise).
"""

from __future__ import annotations

import uuid


def test_response_always_has_request_id(client):
    """N5: every response carries X-Request-ID even when the client does not send one."""
    r = client.get("/health")
    assert "x-request-id" in r.headers
    # Must be a valid UUID
    uuid.UUID(r.headers["x-request-id"])


def test_client_supplied_request_id_is_echoed(client):
    """N5: when the client sends X-Request-ID, the same value is echoed in the response."""
    custom_id = str(uuid.uuid4())
    r = client.get("/health", headers={"X-Request-ID": custom_id})
    assert r.headers["x-request-id"] == custom_id


def test_different_requests_get_different_ids(client):
    """Two requests without X-Request-ID must receive different generated ids."""
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


def test_request_id_on_error_response(client):
    """X-Request-ID is present even on 404 responses."""
    r = client.get("/nonexistent-path")
    assert r.status_code == 404
    assert "x-request-id" in r.headers
