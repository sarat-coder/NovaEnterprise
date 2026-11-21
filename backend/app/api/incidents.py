from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UserContext, get_current_user
from app.repositories.decision_repo import DecisionRepository
from app.repositories.incident_repo import IncidentRepository
from app.schemas.browse import CustomerBrief, DecisionBrief, IncidentDetail, IncidentOut

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    severity: Annotated[str | None, Query(description="Filter by severity")] = None,
    service_id: Annotated[int | None, Query(description="Filter by service id")] = None,
) -> list[IncidentOut]:
    repo = IncidentRepository(db)
    if severity:
        incidents = repo.get_by_severity(severity)
    elif service_id:
        incidents = repo.get_by_service(service_id)
    else:
        incidents = repo.get_all()

    return [
        IncidentOut(
            **{k: v for k, v in vars(inc).items() if not k.startswith("_") and k != "service"},
            service_name=inc.service.name if inc.service else None,
        )
        for inc in incidents
    ]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: int,
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IncidentDetail:
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    customers = repo.get_impacted_customers(incident_id)
    decisions = DecisionRepository(db).get_by_incident(incident_id)

    return IncidentDetail(
        **{
            k: v
            for k, v in vars(incident).items()
            if not k.startswith("_") and k not in ("service", "customer_links", "decision_links")
        },
        service_name=incident.service.name if incident.service else None,
        impacted_customers=[CustomerBrief.model_validate(c) for c in customers],
        decisions=[DecisionBrief.model_validate(d) for d in decisions],
    )
