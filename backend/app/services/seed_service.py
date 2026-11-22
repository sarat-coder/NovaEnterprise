"""Seed the database from sample_data/ JSON files.

Called once at startup (lifespan). Skips rows that already exist so it is safe
to call on every restart.  The seed data lives in sample_data/ at the project root,
one level above the backend/ folder.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.entities import (
    Customer,
    Decision,
    Employee,
    Incident,
    IncidentCustomer,
    IncidentDecision,
    Project,
    Service,
    Team,
    Ticket,
)
from app.models.research import DocumentRecord, MemoryRecord

logger = get_logger(__name__)

# Resolve sample_data/ relative to this file (backend/app/services/seed_service.py → 3 levels up)
_SAMPLE_DATA_DIR = Path(__file__).parent.parent.parent.parent / "sample_data"


def _load(filename: str) -> list[dict]:
    path = _SAMPLE_DATA_DIR / filename
    if not path.exists():
        logger.warning("seed file not found", extra={"path": str(path)})
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def seed(session: Session) -> None:
    """Idempotently seed all sample data into the database."""
    _seed_teams(session)
    _seed_employees(session)
    _seed_services(session)
    _seed_customers(session)
    _seed_incidents(session)
    _seed_decisions(session)
    _seed_projects(session)
    _seed_tickets(session)
    _seed_organizational_memory(session)
    _seed_document_records(session)
    session.commit()
    logger.info("seed complete")


# ---------------------------------------------------------------------------
# Individual seeders
# ---------------------------------------------------------------------------


def _seed_teams(session: Session) -> None:
    for row in _load("teams.json"):
        if session.get(Team, row["id"]):
            continue
        session.add(
            Team(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                description=row.get("description"),
                lead_email=row.get("lead_email"),
            )
        )


def _seed_employees(session: Session) -> None:
    for row in _load("employees.json"):
        if session.get(Employee, row["id"]):
            continue
        session.add(
            Employee(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                title=row.get("title", ""),
                team_id=row.get("team_id"),
            )
        )


def _seed_services(session: Session) -> None:
    for row in _load("services.json"):
        if session.get(Service, row["id"]):
            continue
        session.add(
            Service(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                description=row.get("description"),
                owner_team_id=row.get("owner_team_id"),
                tier=row.get("tier", "tier-2"),
            )
        )


def _seed_customers(session: Session) -> None:
    for row in _load("customers.json"):
        if session.get(Customer, row["id"]):
            continue
        session.add(
            Customer(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                segment=row["segment"],
                industry=row.get("industry"),
                contract_tier=row.get("contract_tier"),
            )
        )


def _seed_incidents(session: Session) -> None:
    from sqlalchemy import select

    for row in _load("incidents.json"):
        if session.get(Incident, row["id"]):
            continue
        inc = Incident(
            id=row["id"],
            incident_id=row["incident_id"],
            title=row["title"],
            severity=row["severity"],
            status=row.get("status", "resolved"),
            service_id=row.get("service_id"),
            root_cause=row.get("root_cause"),
            summary=row.get("summary"),
            started_at=_parse_dt(row.get("started_at")),
            resolved_at=_parse_dt(row.get("resolved_at")),
        )
        session.add(inc)
        session.flush()
        for cust_id in row.get("impacted_customer_ids", []):
            existing = session.execute(
                select(IncidentCustomer).where(
                    IncidentCustomer.incident_id == inc.id,
                    IncidentCustomer.customer_id == cust_id,
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(IncidentCustomer(incident_id=inc.id, customer_id=cust_id))


def _seed_decisions(session: Session) -> None:
    from sqlalchemy import select

    # Build incident_id → pk map
    inc_map: dict[str, int] = {}
    for inc in _load("incidents.json"):
        inc_map[inc["incident_id"]] = inc["id"]

    for row in _load("decisions.json"):
        if session.get(Decision, row["id"]):
            continue
        dec = Decision(
            id=row["id"],
            adr_id=row["adr_id"],
            title=row["title"],
            status=row.get("status", "accepted"),
            context=row.get("context"),
            decision_text=row.get("decision_text"),
            consequences=row.get("consequences"),
            decided_at=_parse_dt(row.get("decided_at")),
        )
        session.add(dec)
        session.flush()
        for inc_id_str in row.get("incident_ids", []):
            inc_pk = inc_map.get(inc_id_str)
            if inc_pk is None:
                continue
            existing = session.execute(
                select(IncidentDecision).where(
                    IncidentDecision.incident_id == inc_pk,
                    IncidentDecision.decision_id == dec.id,
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(IncidentDecision(incident_id=inc_pk, decision_id=dec.id))


def _seed_projects(session: Session) -> None:
    for row in _load("projects.json"):
        if session.get(Project, row["id"]):
            continue
        session.add(
            Project(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                description=row.get("description"),
                status=row.get("status", "active"),
                team_id=row.get("team_id"),
                start_date=_parse_dt(row.get("start_date")),
                end_date=_parse_dt(row.get("end_date")),
            )
        )


def _seed_tickets(session: Session) -> None:
    for row in _load("tickets.json"):
        if session.get(Ticket, row["id"]):
            continue
        session.add(
            Ticket(
                id=row["id"],
                ticket_id=row["ticket_id"],
                title=row["title"],
                description=row.get("description"),
                status=row.get("status", "open"),
                priority=row.get("priority", "medium"),
                project_id=row.get("project_id"),
                assignee_id=row.get("assignee_id"),
                story_points=row.get("story_points"),
            )
        )


def _seed_organizational_memory(session: Session) -> None:
    from sqlalchemy import select

    existing = session.execute(
        select(MemoryRecord).where(
            MemoryRecord.scope == "organizational",
            MemoryRecord.key == "fiscal_calendar",
        )
    ).scalar_one_or_none()
    if existing:
        return

    data = _load("organizational_memory.json")
    if not data:
        return

    for key, value in data.items():
        session.add(
            MemoryRecord(
                id=str(uuid.uuid4()),
                scope="organizational",
                owner_id=None,
                key=key,
                value=json.dumps(value),
                source="sample_data/organizational_memory.json",
            )
        )


def _seed_document_records(session: Session) -> None:
    """Create a DocumentRecord row for each sample document file."""
    from sqlalchemy import select

    docs_dir = _SAMPLE_DATA_DIR / "documents"
    if not docs_dir.exists():
        return
    for doc_path in sorted(docs_dir.glob("*.md")):
        existing = (
            session.execute(select(DocumentRecord).where(DocumentRecord.filename == doc_path.name))
            .scalars()
            .first()
        )
        if existing:
            continue
        content = doc_path.read_text(encoding="utf-8")
        is_hostile = doc_path.name == "vendor-note-processor-update.md"
        session.add(
            DocumentRecord(
                id=str(uuid.uuid4()),
                filename=doc_path.name,
                source_path=str(doc_path),
                content_type="text/markdown",
                size_bytes=len(content.encode()),
                status="indexed",
                chunk_count=0,
                uploaded_by="system",
                flagged=is_hostile,
                flag_reason="prompt-injection-attempt" if is_hostile else None,
            )
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
