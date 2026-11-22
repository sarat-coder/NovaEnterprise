"""Memory API schemas (Phase 10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MemoryRecordIn(BaseModel):
    """Body for creating/updating an analyst memory note."""

    key: str
    value: str


class MemoryRecordOut(BaseModel):
    """A single analyst memory record returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: str
    key: str
    value: str
    source: str | None = None
    updated_at: datetime


class OrganizationalMemoryOut(BaseModel):
    """Organizational memory facts."""

    fiscal_calendar: dict[str, Any]
    sla_definitions: dict[str, Any]
    severity_definitions: dict[str, Any]
    data_retention_policy: dict[str, Any]
    on_call_rotation: dict[str, Any]
    key_contacts: dict[str, Any]


class QuarterResolutionOut(BaseModel):
    """Result of resolving a quarter label to concrete dates."""

    quarter: str
    label: str
    start_date: str
    end_date: str
    year: int
