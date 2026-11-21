from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Employee, Service, Team


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[Team]:
        return list(self._session.execute(select(Team)).scalars())

    def get_by_id(self, team_id: int) -> Team | None:
        return self._session.get(Team, team_id)

    def get_by_slug(self, slug: str) -> Team | None:
        stmt = select(Team).where(Team.slug == slug)
        return self._session.execute(stmt).scalar_one_or_none()

    def count(self) -> int:
        return self._session.query(Team).count()

    def get_employees(self, team_id: int) -> list[Employee]:
        stmt = select(Employee).where(Employee.team_id == team_id)
        return list(self._session.execute(stmt).scalars())

    def get_services(self, team_id: int) -> list[Service]:
        stmt = select(Service).where(Service.owner_team_id == team_id)
        return list(self._session.execute(stmt).scalars())
