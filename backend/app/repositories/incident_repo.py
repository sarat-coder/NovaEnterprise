from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Customer, Incident, IncidentCustomer


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[Incident]:
        return list(self._session.execute(select(Incident)).scalars())

    def get_by_id(self, incident_id: int) -> Incident | None:
        return self._session.get(Incident, incident_id)

    def get_by_incident_id(self, incident_id: str) -> Incident | None:
        stmt = select(Incident).where(Incident.incident_id == incident_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_service(self, service_id: int) -> list[Incident]:
        stmt = select(Incident).where(Incident.service_id == service_id)
        return list(self._session.execute(stmt).scalars())

    def get_by_service_and_date_range(
        self,
        service_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Incident]:
        stmt = (
            select(Incident)
            .where(Incident.service_id == service_id)
            .where(Incident.started_at >= start)
            .where(Incident.started_at <= end)
        )
        return list(self._session.execute(stmt).scalars())

    def get_by_severity(self, severity: str) -> list[Incident]:
        stmt = select(Incident).where(Incident.severity == severity)
        return list(self._session.execute(stmt).scalars())

    def get_impacted_customers(self, incident_pk: int) -> list[Customer]:
        stmt = (
            select(Customer)
            .join(IncidentCustomer, IncidentCustomer.customer_id == Customer.id)
            .where(IncidentCustomer.incident_id == incident_pk)
        )
        return list(self._session.execute(stmt).scalars())

    def count(self) -> int:
        return self._session.query(Incident).count()
