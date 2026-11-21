"""
Shared pytest fixtures.

All tests run fully offline:
  LLM_PROVIDER=fake, VECTOR_STORE=memory, GRAPH_STORE=memory, SQLite, fakeredis.
Never introduce a fixture that opens a real network connection.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force offline settings before the app module is imported.
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("GRAPH_STORE", "memory")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("REDIS_URL", "")  # → fakeredis
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")


@pytest.fixture(autouse=True)
def _reset_settings():
    """Clear the lru_cache before and after every test so env changes take effect."""
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture(scope="session")
def app():
    """Return the FastAPI application instance (session-scoped, created once)."""
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    """Synchronous TestClient around the app. Runs lifespan on entry."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
