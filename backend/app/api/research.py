"""Research API — POST start, GET poll, GET events (P12-4, F1, F16).

POST /api/v1/research          → 202 {session_id, status: "running"}
GET  /api/v1/research/{id}     → ResearchSessionOut
GET  /api/v1/research/{id}/events → list[WorkflowEventOut]
"""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.security import UserContext, require_role
from app.schemas.research import (
    ResearchRequest,
    ResearchSessionOut,
    ResearchStarted,
    WorkflowEventOut,
)
from app.services.research_service import get_research_service

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post("", status_code=202, response_model=ResearchStarted)
def start_research(
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: UserContext = Depends(require_role("analyst")),
) -> ResearchStarted:
    """Start a research session. Returns 202 immediately; work runs in background."""
    service = get_research_service()
    session_id = service.create_session(
        question=body.question,
        user_id=current_user.sub,
    )
    background_tasks.add_task(service.start_research, session_id, body.question)
    return ResearchStarted(session_id=session_id, status="running")


@router.get("/{session_id}", response_model=ResearchSessionOut)
def get_session(
    session_id: str,
    current_user: UserContext = Depends(require_role("viewer")),
) -> ResearchSessionOut:
    """Poll the current state of a research session."""
    service = get_research_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found")

    # Reconstruct evidence from events (stored as JSON in event payloads)
    # For now, evidence is tracked via evidence_count on the session
    strategies = json.loads(session.strategies_used or "[]")

    return ResearchSessionOut(
        session_id=session.id,
        question=session.question,
        status=session.status,
        complexity=session.complexity,
        strategies_used=strategies,
        sub_questions=[],
        evidence=[],
        answer=session.answer,
        citations_valid=None,
        evidence_count=session.evidence_count,
        citation_count=session.citation_count,
        corrective_rounds=session.corrective_rounds,
        error=session.error,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


@router.get("/{session_id}/events", response_model=list[WorkflowEventOut])
def get_events(
    session_id: str,
    current_user: UserContext = Depends(require_role("viewer")),
) -> list[WorkflowEventOut]:
    """Return the full event timeline for a research session (F16)."""
    service = get_research_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found")

    events = service.get_events(session_id)
    return [
        WorkflowEventOut(
            id=ev.id,
            node=ev.node,
            event_type=ev.event_type,
            payload=json.loads(ev.payload or "{}"),
            duration_ms=ev.duration_ms,
            occurred_at=ev.occurred_at,
        )
        for ev in events
    ]
