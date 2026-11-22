"""Unit tests for the four memory scopes (Phase 10, F15).

Covers:
  - Organizational scope: get_all, resolve_quarter ("last quarter", Q-label)
  - Conversation scope: add_turn, get_turns, clear (via fakeredis)
  - Session scope: upsert, get_all, clear (via SQLite)
  - Analyst scope: upsert, get_all, delete, ownership isolation
"""

from __future__ import annotations

import os
from datetime import date

import fakeredis
import pytest

# Force offline settings before any app import
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("GRAPH_STORE", "memory")
os.environ.setdefault("REDIS_URL", "")

from memory.scopes import analyst as analyst_scope
from memory.scopes import conversation as conv_scope
from memory.scopes import organizational as org_scope
from memory.scopes import session as session_scope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def db_session():
    """In-memory SQLite session with MemoryRecord table created."""
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from app.models.base import Base
    from app.models.research import MemoryRecord  # noqa: F401 — registers the table

    engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        yield s


# ---------------------------------------------------------------------------
# Organizational scope
# ---------------------------------------------------------------------------


def test_org_get_all_has_fiscal_calendar():
    """N1: organizational memory loads offline from JSON."""
    data = org_scope.get_all()
    assert "fiscal_calendar" in data
    assert "quarters" in data["fiscal_calendar"]


def test_org_resolve_last_quarter():
    """Resolves 'last quarter' relative to a known date."""
    # 2026-11-22 → Q4 is current → last quarter is Q3 (Jul–Sep 2026)
    result = org_scope.resolve_quarter("last quarter", reference_date=date(2026, 11, 22))
    assert result["quarter"] == "Q3"
    assert result["year"] == 2026
    assert result["start_date"] == "2026-07-01"
    assert result["end_date"] == "2026-09-30"


def test_org_resolve_q1():
    """Resolves 'Q1' in the current year."""
    result = org_scope.resolve_quarter("Q1", reference_date=date(2026, 11, 22))
    assert result["quarter"] == "Q1"
    assert result["start_date"].endswith("-01-01")


def test_org_resolve_this_quarter():
    """'this quarter' returns the current quarter."""
    # 2026-11-22 → Q4
    result = org_scope.resolve_quarter("this quarter", reference_date=date(2026, 11, 22))
    assert result["quarter"] == "Q4"


def test_org_resolve_last_quarter_wraps_year():
    """'last quarter' at Q1 wraps to Q4 of the previous year."""
    result = org_scope.resolve_quarter("last quarter", reference_date=date(2026, 2, 15))
    assert result["quarter"] == "Q4"
    assert result["year"] == 2025


def test_org_resolve_bad_label():
    with pytest.raises(ValueError, match="Unrecognised"):
        org_scope.resolve_quarter("fortnight ago")


def test_org_sla_definitions_present():
    data = org_scope.get_all()
    assert "tier-1" in data["sla_definitions"]
    assert "tier-2" in data["sla_definitions"]


# ---------------------------------------------------------------------------
# Conversation scope
# ---------------------------------------------------------------------------


def test_conv_add_and_get(redis_client):
    """F15: conversation turns are stored and retrieved in order."""
    conv_scope.add_turn(redis_client, "sess-1", "user", "What happened?")
    conv_scope.add_turn(redis_client, "sess-1", "assistant", "Here is the summary.")
    turns = conv_scope.get_turns(redis_client, "sess-1")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"


def test_conv_clear(redis_client):
    conv_scope.add_turn(redis_client, "sess-2", "user", "Hello")
    conv_scope.clear(redis_client, "sess-2")
    assert conv_scope.get_turns(redis_client, "sess-2") == []


def test_conv_sessions_isolated(redis_client):
    conv_scope.add_turn(redis_client, "sess-A", "user", "Question A")
    conv_scope.add_turn(redis_client, "sess-B", "user", "Question B")
    assert len(conv_scope.get_turns(redis_client, "sess-A")) == 1
    assert len(conv_scope.get_turns(redis_client, "sess-B")) == 1


# ---------------------------------------------------------------------------
# Session scope
# ---------------------------------------------------------------------------


def test_session_upsert_and_get(db_session):
    """F15: session facts are stored and retrieved."""
    session_scope.upsert(db_session, "run-1", "entity.service", "Payments API")
    facts = session_scope.get_all(db_session, "run-1")
    assert len(facts) == 1
    assert facts[0].key == "entity.service"
    assert facts[0].value == "Payments API"


def test_session_upsert_overwrites(db_session):
    session_scope.upsert(db_session, "run-2", "quarter", "Q3")
    session_scope.upsert(db_session, "run-2", "quarter", "Q4")
    facts = session_scope.get_all(db_session, "run-2")
    assert len(facts) == 1
    assert facts[0].value == "Q4"


def test_session_clear(db_session):
    session_scope.upsert(db_session, "run-3", "k", "v")
    count = session_scope.clear(db_session, "run-3")
    assert count == 1
    assert session_scope.get_all(db_session, "run-3") == []


def test_session_isolation(db_session):
    session_scope.upsert(db_session, "run-X", "k", "v")
    assert session_scope.get_all(db_session, "run-Y") == []


# ---------------------------------------------------------------------------
# Analyst scope — ownership enforcement
# ---------------------------------------------------------------------------


def test_analyst_upsert_and_get(db_session):
    """F15: analyst notes are stored and retrieved."""
    analyst_scope.upsert(db_session, "alice", "preference.format", "bullet_points")
    notes = analyst_scope.get_all(db_session, "alice")
    assert len(notes) == 1
    assert notes[0].key == "preference.format"


def test_analyst_cannot_see_other_analyst_notes(db_session):
    """Ownership: alice's notes are not visible to bob."""
    analyst_scope.upsert(db_session, "alice", "secret", "my note")
    assert analyst_scope.get_all(db_session, "bob") == []


def test_analyst_delete_own_note(db_session):
    record = analyst_scope.upsert(db_session, "alice", "temp", "value")
    assert analyst_scope.delete(db_session, record.id, "alice") is True
    assert analyst_scope.get_all(db_session, "alice") == []


def test_analyst_cannot_delete_other_note(db_session):
    record = analyst_scope.upsert(db_session, "alice", "k", "v")
    assert analyst_scope.delete(db_session, record.id, "bob") is False
    # alice's note still exists
    assert len(analyst_scope.get_all(db_session, "alice")) == 1


def test_analyst_upsert_overwrites(db_session):
    analyst_scope.upsert(db_session, "carol", "note", "v1")
    analyst_scope.upsert(db_session, "carol", "note", "v2")
    notes = analyst_scope.get_all(db_session, "carol")
    assert len(notes) == 1
    assert notes[0].value == "v2"
