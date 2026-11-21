from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Decision, IncidentDecision


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[Decision]:
        return list(self._session.execute(select(Decision)).scalars())

    def get_by_id(self, decision_id: int) -> Decision | None:
        return self._session.get(Decision, decision_id)

    def get_by_adr_id(self, adr_id: str) -> Decision | None:
        stmt = select(Decision).where(Decision.adr_id == adr_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_incident(self, incident_pk: int) -> list[Decision]:
        stmt = (
            select(Decision)
            .join(IncidentDecision, IncidentDecision.decision_id == Decision.id)
            .where(IncidentDecision.incident_id == incident_pk)
        )
        return list(self._session.execute(stmt).scalars())

    def count(self) -> int:
        return self._session.query(Decision).count()
