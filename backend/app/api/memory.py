"""Memory API — analyst-owned notes and organizational memory (P10-4).

F15: Four separated memory scopes surfaced per session.

Endpoints:
  GET    /api/v1/memory/organizational         viewer+   shared company facts
  GET    /api/v1/memory/organizational/quarter  viewer+   last-quarter resolution
  GET    /api/v1/memory/notes                  analyst+  list own notes
  POST   /api/v1/memory/notes                  analyst+  add a note
  DELETE /api/v1/memory/notes/{id}             analyst+  delete own note
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Role, UserContext, require_role
from app.schemas.memory import (
    MemoryRecordIn,
    MemoryRecordOut,
    OrganizationalMemoryOut,
    QuarterResolutionOut,
)
from memory import memory_service

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# ---------------------------------------------------------------------------
# Organizational memory (read-only, any authenticated user)
# ---------------------------------------------------------------------------


@router.get("/organizational", response_model=OrganizationalMemoryOut)
def get_organizational_memory(
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
) -> OrganizationalMemoryOut:
    data = memory_service.get_organizational_memory()
    return OrganizationalMemoryOut(**data)


@router.get("/organizational/quarter", response_model=QuarterResolutionOut)
def resolve_last_quarter(
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
) -> QuarterResolutionOut:
    result = memory_service.resolve_last_quarter()
    return QuarterResolutionOut(**result)


# ---------------------------------------------------------------------------
# Analyst notes (analyst-owned, ownership enforced per record)
# ---------------------------------------------------------------------------


@router.get("/notes", response_model=list[MemoryRecordOut])
def list_notes(
    user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
) -> list[MemoryRecordOut]:
    analyst_id = user.user_id or user.sub
    from memory.scopes.analyst import get_all  # noqa: PLC0415

    records = get_all(db, analyst_id)
    return [MemoryRecordOut.model_validate(r) for r in records]


@router.post("/notes", response_model=MemoryRecordOut, status_code=status.HTTP_201_CREATED)
def add_note(
    body: MemoryRecordIn,
    user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryRecordOut:
    analyst_id = user.user_id or user.sub
    from memory.scopes.analyst import upsert  # noqa: PLC0415

    record = upsert(db, analyst_id, body.key, body.value, source="analyst_api")
    return MemoryRecordOut.model_validate(record)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    analyst_id = user.user_id or user.sub
    deleted = memory_service.delete_analyst_note(db, note_id, analyst_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found or not owned by you",
        )
