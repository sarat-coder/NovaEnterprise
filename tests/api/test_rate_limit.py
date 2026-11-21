"""
Tests for the token-bucket rate limiter middleware.

Covers:
  P3-3 — rate limit returns 429 after RATE_LIMIT_PER_MINUTE requests
  Phase 3 exit criterion — works on fakeredis when REDIS_URL is empty (N6)
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _flush_redis():
    """Flush fakeredis state before and after each test to prevent counter bleed-through."""

    def _flush():
        try:
            from app.core.redis_client import get_redis_client

            get_redis_client().flushall()
        except Exception:  # noqa: BLE001
            pass

    _flush()
    yield
    _flush()


@pytest.fixture
def low_limit_client(app):
    """TestClient with RATE_LIMIT_PER_MINUTE=3 so we can hit the limit cheaply."""
    from fastapi.testclient import TestClient

    os.environ["RATE_LIMIT_PER_MINUTE"] = "3"
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    del os.environ["RATE_LIMIT_PER_MINUTE"]
    reset_settings_cache()


def test_rate_limit_allows_requests_within_limit(low_limit_client):
    """The first N requests within the limit all succeed (N6)."""
    for _ in range(3):
        r = low_limit_client.get("/health")
        assert r.status_code == 200


def test_rate_limit_returns_429_when_exceeded(low_limit_client):
    """The (limit + 1)th request in the same minute window → 429."""
    for _ in range(3):
        low_limit_client.get("/health")
    r = low_limit_client.get("/health")
    assert r.status_code == 429
    assert "detail" in r.json()


def test_rate_limit_429_body_is_json(low_limit_client):
    """The 429 response body is valid JSON with a detail field."""
    for _ in range(4):
        r = low_limit_client.get("/health")
    assert r.status_code == 429
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)
