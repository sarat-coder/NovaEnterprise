from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research import ResearchSession, WorkflowEvent


class ResearchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_session(self, session: ResearchSession) -> ResearchSession:
        self._session.add(session)
        self._session.flush()
        return session

    def get_session(self, session_id: str) -> ResearchSession | None:
        return self._session.get(ResearchSession, session_id)

    def update_session(self, session: ResearchSession) -> ResearchSession:
        self._session.merge(session)
        self._session.flush()
        return session

    def get_sessions_by_user(self, user_id: str) -> list[ResearchSession]:
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(ResearchSession.started_at.desc())
        )
        return list(self._session.execute(stmt).scalars())

    def add_event(self, event: WorkflowEvent) -> WorkflowEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def get_events(self, session_id: str) -> list[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.session_id == session_id)
            .order_by(WorkflowEvent.occurred_at.asc())
        )
        return list(self._session.execute(stmt).scalars())
