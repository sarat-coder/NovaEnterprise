from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UserContext, get_current_user
from app.repositories.customer_repo import CustomerRepository
from app.schemas.browse import CustomerOut

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CustomerOut]:
    repo = CustomerRepository(db)
    return [CustomerOut.model_validate(c) for c in repo.get_all()]


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerOut:
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerOut.model_validate(customer)
