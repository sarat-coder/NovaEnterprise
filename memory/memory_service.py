"""Memory service — unified interface for all four scopes (F15).

Surfaces four separated scopes per session:
  organizational  shared company facts (read-only, from JSON)
  conversation    per-session turns (Redis / fakeredis)
  session         facts extracted during one research run (DB)
  analyst         personal notes owned by an analyst (DB)

Memory is NEVER mixed with retrieval and NEVER cited as evidence.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from memory.scopes import analyst as analyst_scope
from memory.scopes import conversation as conv_scope
from memory.scopes import organizational as org_scope
from memory.scopes import session as session_scope

# ---------------------------------------------------------------------------
# Organizational scope (read-only)
# ---------------------------------------------------------------------------


def get_organizational_memory() -> dict[str, Any]:
    """Return the full organizational memory dict."""
    return org_scope.get_all()


def resolve_last_quarter(reference_date: date | None = None) -> dict[str, Any]:
    """Resolve 'last quarter' to concrete start/end dates using the fiscal calendar."""
    return org_scope.resolve_quarter("last quarter", reference_date)


def resolve_quarter(label: str, reference_date: date | None = None) -> dict[str, Any]:
    """Resolve any quarter label (e.g. 'Q3', 'this quarter') to start/end dates."""
    return org_scope.resolve_quarter(label, reference_date)


# ---------------------------------------------------------------------------
# Conversation scope (Redis)
# ---------------------------------------------------------------------------


def add_conversation_turn(
    redis_client: Any,
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Append a user or assistant turn to the session's conversation history."""
    conv_scope.add_turn(redis_client, session_id, role, content)


def get_conversation(redis_client: Any, session_id: str) -> list[dict[str, str]]:
    """Return all conversation turns for a session."""
    return conv_scope.get_turns(redis_client, session_id)


def clear_conversation(redis_client: Any, session_id: str) -> None:
    """Clear the conversation history for a session."""
    conv_scope.clear(redis_client, session_id)


# ---------------------------------------------------------------------------
# Session scope (DB, keyed by research session id)
# ---------------------------------------------------------------------------


def upsert_session_fact(db: Session, session_id: str, key: str, value: str) -> None:
    """Write or update a fact for the current research session."""
    session_scope.upsert(db, session_id, key, value, source="research_workflow")


def get_session_facts(db: Session, session_id: str) -> list[dict[str, str]]:
    """Return all session-scoped facts as a list of {key, value} dicts."""
    records = session_scope.get_all(db, session_id)
    return [{"key": r.key, "value": r.value, "source": r.source or ""} for r in records]


# ---------------------------------------------------------------------------
# Analyst scope (DB, keyed by analyst user_id)
# ---------------------------------------------------------------------------


def upsert_analyst_note(db: Session, analyst_id: str, key: str, value: str) -> None:
    """Write or update a personal note for an analyst."""
    analyst_scope.upsert(db, analyst_id, key, value, source="analyst")


def get_analyst_notes(db: Session, analyst_id: str) -> list[dict[str, Any]]:
    """Return all notes owned by this analyst."""
    records = analyst_scope.get_all(db, analyst_id)
    return [
        {
            "id": r.id,
            "key": r.key,
            "value": r.value,
            "source": r.source or "",
            "updated_at": r.updated_at.isoformat(),
        }
        for r in records
    ]


def delete_analyst_note(db: Session, record_id: str, analyst_id: str) -> bool:
    """Delete a note if it belongs to this analyst. Returns True if deleted."""
    return analyst_scope.delete(db, record_id, analyst_id)


# ---------------------------------------------------------------------------
# Session summary — all four scopes for one research session
# ---------------------------------------------------------------------------


def get_session_memory_summary(
    db: Session,
    redis_client: Any,
    session_id: str,
    analyst_id: str | None = None,
) -> dict[str, Any]:
    """Return all four memory scopes for a session in one call.

    Used by the research workflow to surface memory context and by the
    UI to populate the memory panel on the research/[id] page.
    """
    summary: dict[str, Any] = {
        "organizational": {
            "fiscal_calendar": org_scope.get_all().get("fiscal_calendar"),
            "last_quarter": org_scope.resolve_quarter("last quarter"),
        },
        "conversation": conv_scope.get_turns(redis_client, session_id),
        "session": get_session_facts(db, session_id),
        "analyst": get_analyst_notes(db, analyst_id) if analyst_id else [],
    }
    return summary
