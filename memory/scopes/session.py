"""Session memory scope — facts extracted during a single research run.

Backed by the `memory_records` table with scope='session'.
owner_id is the research session id; each record is a key/value pair.

These are cleared (or archived) when a session ends; they are never
mixed with retrieval and never cited as evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.research import MemoryRecord


def upsert(db: Session, session_id: str, key: str, value: str, source: str = "") -> MemoryRecord:
    """Write or update a session-scoped fact."""
    existing = (
        db.query(MemoryRecord).filter_by(scope="session", owner_id=session_id, key=key).first()
    )
    if existing:
        existing.value = value
        existing.source = source
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    record = MemoryRecord(
        id=str(uuid.uuid4()),
        scope="session",
        owner_id=session_id,
        key=key,
        value=value,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_all(db: Session, session_id: str) -> list[MemoryRecord]:
    """Return all session-scoped facts for a research session."""
    return db.query(MemoryRecord).filter_by(scope="session", owner_id=session_id).all()


def clear(db: Session, session_id: str) -> int:
    """Delete all session-scoped facts for a session. Returns count deleted."""
    count = db.query(MemoryRecord).filter_by(scope="session", owner_id=session_id).delete()
    db.commit()
    return count
