from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UserContext, get_current_user
from app.repositories.decision_repo import DecisionRepository
from app.repositories.incident_repo import IncidentRepository
from app.schemas.browse import DecisionDetail, DecisionOut, IncidentBrief

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get("", response_model=list[DecisionOut])
def list_decisions(
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DecisionOut]:
    repo = DecisionRepository(db)
    return [DecisionOut.model_validate(d) for d in repo.get_all()]


@router.get("/{decision_id}", response_model=DecisionDetail)
def get_decision(
    decision_id: int,
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DecisionDetail:
    repo = DecisionRepository(db)
    decision = repo.get_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    incident_repo = IncidentRepository(db)
    all_incidents = incident_repo.get_all()
    linked = [
        IncidentBrief.model_validate(inc)
        for inc in all_incidents
        if any(link.decision_id == decision_id for link in inc.decision_links)
    ]

    return DecisionDetail(
        **{
            k: v
            for k, v in vars(decision).items()
            if not k.startswith("_") and k != "incident_links"
        },
        incidents=linked,
    )
