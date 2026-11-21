from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    lead_email: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employees: Mapped[list[Employee]] = relationship("Employee", back_populates="team")
    services: Mapped[list[Service]] = relationship("Service", back_populates="owner_team")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Team | None] = relationship("Team", back_populates="employees")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    tier: Mapped[str] = mapped_column(String(20), default="tier-2")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner_team: Mapped[Team | None] = relationship("Team", back_populates="services")
    incidents: Mapped[list[Incident]] = relationship("Incident", back_populates="service")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    segment: Mapped[str] = mapped_column(String(40))  # enterprise / mid-market / smb
    industry: Mapped[str | None] = mapped_column(String(100))
    contract_tier: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident_links: Mapped[list[IncidentCustomer]] = relationship(
        "IncidentCustomer", back_populates="customer"
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(10))  # SEV1 / SEV2 / SEV3
    status: Mapped[str] = mapped_column(String(20), default="resolved")
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    root_cause: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    service: Mapped[Service | None] = relationship("Service", back_populates="incidents")
    customer_links: Mapped[list[IncidentCustomer]] = relationship(
        "IncidentCustomer", back_populates="incident"
    )
    decision_links: Mapped[list[IncidentDecision]] = relationship(
        "IncidentDecision", back_populates="incident"
    )


class IncidentCustomer(Base):
    __tablename__ = "incident_customers"

    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    impact_description: Mapped[str | None] = mapped_column(Text)

    incident: Mapped[Incident] = relationship("Incident", back_populates="customer_links")
    customer: Mapped[Customer] = relationship("Customer", back_populates="incident_links")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adr_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="accepted"
    )  # proposed / accepted / deprecated
    context: Mapped[str | None] = mapped_column(Text)
    decision_text: Mapped[str | None] = mapped_column(Text)
    consequences: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident_links: Mapped[list[IncidentDecision]] = relationship(
        "IncidentDecision", back_populates="decision"
    )


class IncidentDecision(Base):
    __tablename__ = "incident_decisions"

    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), primary_key=True)

    incident: Mapped[Incident] = relationship("Incident", back_populates="decision_links")
    decision: Mapped[Decision] = relationship("Decision", back_populates="incident_links")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active")
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tickets: Mapped[list[Ticket]] = relationship("Ticket", back_populates="project")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    story_points: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)

    project: Mapped[Project | None] = relationship("Project", back_populates="tickets")
    assignee: Mapped[Employee | None] = relationship("Employee")
