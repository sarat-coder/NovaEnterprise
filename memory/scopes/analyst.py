"""Analyst memory scope — personal notes and preferences owned by an analyst.

Backed by the `memory_records` table with scope='analyst'.
owner_id is the analyst's user_id from their JWT.

Analysts can only read and write their own records; the ownership check
is enforced here and in the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.research import MemoryRecord


def upsert(db: Session, analyst_id: str, key: str, value: str, source: str = "") -> MemoryRecord:
    """Write or update an analyst-scoped fact."""
    existing = (
        db.query(MemoryRecord).filter_by(scope="analyst", owner_id=analyst_id, key=key).first()
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
        scope="analyst",
        owner_id=analyst_id,
        key=key,
        value=value,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_all(db: Session, analyst_id: str) -> list[MemoryRecord]:
    """Return all analyst-scoped facts owned by this analyst."""
    return db.query(MemoryRecord).filter_by(scope="analyst", owner_id=analyst_id).all()


def get_one(db: Session, record_id: str, analyst_id: str) -> MemoryRecord | None:
    """Return one record only if it belongs to this analyst."""
    return (
        db.query(MemoryRecord).filter_by(id=record_id, scope="analyst", owner_id=analyst_id).first()
    )


def delete(db: Session, record_id: str, analyst_id: str) -> bool:
    """Delete a record if it belongs to this analyst. Returns True if deleted."""
    record = get_one(db, record_id, analyst_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True
