from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Customer


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> list[Customer]:
        return list(self._session.execute(select(Customer)).scalars())

    def get_by_id(self, customer_id: int) -> Customer | None:
        return self._session.get(Customer, customer_id)

    def get_by_slug(self, slug: str) -> Customer | None:
        stmt = select(Customer).where(Customer.slug == slug)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_segment(self, segment: str) -> list[Customer]:
        stmt = select(Customer).where(Customer.segment == segment)
        return list(self._session.execute(stmt).scalars())

    def count(self) -> int:
        return self._session.query(Customer).count()
