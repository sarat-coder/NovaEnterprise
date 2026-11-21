"""Tests that the seed service populates the expected row counts (Phase 2, N1).

Exit criterion from PLAN_PHASE.md Phase 2:
  6 teams, 20 employees, 8 services, 10 customers, 12 incidents, 8 decisions,
  6 projects, 15 tickets, 15 documents, organizational memory records.

The `client` fixture (from conftest.py) starts the FastAPI lifespan which calls
init_db() and seed(), so the DB is ready when these tests run.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def db_session(app):
    """Return a live SQLAlchemy session against the test database.

    The app fixture is session-scoped; using it here avoids re-importing.
    We call init_db() and seed() directly to ensure the test DB is populated
    without depending on the lifespan (which is not guaranteed to run when
    using the app fixture alone without TestClient context).
    """

    from app.core.db import get_session_factory, init_db
    from app.services.seed_service import seed

    init_db()
    factory = get_session_factory()
    session = factory()
    seed(session)
    yield session
    session.close()


def test_team_count(db_session):
    """Seed loads exactly 6 teams (CLAUDE.md §5)."""
    from app.models.entities import Team

    assert db_session.query(Team).count() == 6


def test_employee_count(db_session):
    """Seed loads exactly 20 employees."""
    from app.models.entities import Employee

    assert db_session.query(Employee).count() == 20


def test_service_count(db_session):
    """Seed loads exactly 8 services."""
    from app.models.entities import Service

    assert db_session.query(Service).count() == 8


def test_customer_count(db_session):
    """Seed loads exactly 10 customers."""
    from app.models.entities import Customer

    assert db_session.query(Customer).count() == 10


def test_incident_count(db_session):
    """Seed loads exactly 12 incidents."""
    from app.models.entities import Incident

    assert db_session.query(Incident).count() == 12


def test_decision_count(db_session):
    """Seed loads exactly 8 decisions."""
    from app.models.entities import Decision

    assert db_session.query(Decision).count() == 8


def test_project_count(db_session):
    """Seed loads exactly 6 projects."""
    from app.models.entities import Project

    assert db_session.query(Project).count() == 6


def test_ticket_count(db_session):
    """Seed loads exactly 15 tickets."""
    from app.models.entities import Ticket

    assert db_session.query(Ticket).count() == 15


def test_document_count(db_session):
    """Seed registers exactly 15 document records."""
    from app.models.research import DocumentRecord

    assert db_session.query(DocumentRecord).count() == 15


def test_vendor_note_flagged(db_session):
    """The vendor-note document is flagged as a prompt-injection attempt."""
    from sqlalchemy import select

    from app.models.research import DocumentRecord

    doc = db_session.execute(
        select(DocumentRecord).where(DocumentRecord.filename == "vendor-note-processor-update.md")
    ).scalar_one()
    assert doc.flagged is True
    assert doc.flag_reason == "prompt-injection-attempt"


def test_key_postmortem_indexed(db_session):
    """The canonical-question postmortem (INC-2031) is indexed as a document."""
    from sqlalchemy import select

    from app.models.research import DocumentRecord

    doc = db_session.execute(
        select(DocumentRecord).where(
            DocumentRecord.filename == "postmortem-inc-2031-payments-api-outage.md"
        )
    ).scalar_one()
    assert doc.flagged is False


def test_incident_customer_links(db_session):
    """INC-2031 (id=8) is linked to 5 impacted customers."""
    from app.models.entities import IncidentCustomer

    links = db_session.query(IncidentCustomer).filter_by(incident_id=8).count()
    assert links == 5


def test_organizational_memory_seeded(db_session):
    """Organizational memory records are seeded from organizational_memory.json."""
    from app.models.research import MemoryRecord

    count = db_session.query(MemoryRecord).filter_by(scope="organizational").count()
    assert count >= 1


def test_seed_idempotent(db_session):
    """Running seed a second time on the same DB does not duplicate rows."""
    from app.models.entities import Team
    from app.services.seed_service import seed

    seed(db_session)
    assert db_session.query(Team).count() == 6


def test_health_ready_includes_database(client):
    """GET /health/ready reports database: ok (sqlite) after DB initialisation (N1)."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    db_check = body["checks"].get("database", {})
    assert db_check.get("status") == "ok"
    assert "sqlite" in db_check.get("detail", "")
