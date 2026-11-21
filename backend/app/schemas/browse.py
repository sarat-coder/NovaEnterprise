from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Customer schemas
# ---------------------------------------------------------------------------


class CustomerOut(BaseModel):
    id: int
    name: str
    slug: str
    segment: str
    industry: str | None
    contract_tier: str | None

    model_config = {"from_attributes": True}


class CustomerBrief(BaseModel):
    id: int
    name: str
    slug: str
    segment: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Incident schemas
# ---------------------------------------------------------------------------


class IncidentOut(BaseModel):
    id: int
    incident_id: str
    title: str
    severity: str
    status: str
    service_id: int | None
    service_name: str | None = None
    root_cause: str | None
    summary: str | None
    started_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class IncidentBrief(BaseModel):
    id: int
    incident_id: str
    title: str
    severity: str

    model_config = {"from_attributes": True}


class IncidentDetail(IncidentOut):
    impacted_customers: list[CustomerBrief] = []
    decisions: list[DecisionBrief] = []


# ---------------------------------------------------------------------------
# Decision schemas
# ---------------------------------------------------------------------------


class DecisionOut(BaseModel):
    id: int
    adr_id: str
    title: str
    status: str
    context: str | None
    decision_text: str | None
    consequences: str | None
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class DecisionBrief(BaseModel):
    id: int
    adr_id: str
    title: str
    status: str

    model_config = {"from_attributes": True}


class DecisionDetail(DecisionOut):
    incidents: list[IncidentBrief] = []


# Fix forward references
IncidentDetail.model_rebuild()
