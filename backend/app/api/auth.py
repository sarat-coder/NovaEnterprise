from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import Role, UserContext, create_access_token, get_current_user, require_role

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Demo users: username → (password, role)
_DEMO_USERS: dict[str, tuple[str, Role]] = {
    "viewer": ("viewer123", Role.VIEWER),
    "analyst": ("analyst123", Role.ANALYST),
    "admin": ("admin123", Role.ADMIN),
}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    """Issue a JWT for one of the three demo users (viewer / analyst / admin)."""
    entry = _DEMO_USERS.get(body.username)
    if entry is None or entry[0] != body.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = entry[1]
    token = create_access_token(sub=body.username, role=role, user_id=body.username)
    return TokenResponse(access_token=token, token_type="bearer", role=role.name.lower())


@router.get("/me")
def get_me(user: Annotated[UserContext, Depends(get_current_user)]) -> dict:
    """Return the current user's context. Requires any authenticated role (viewer+)."""
    return {"sub": user.sub, "role": user.role.name.lower(), "user_id": user.user_id}


@router.get("/analyst-only")
def analyst_only(_: Annotated[UserContext, Depends(require_role(Role.ANALYST))]) -> dict:
    """Analyst-or-above endpoint used to verify RBAC in Phase 3 tests."""
    return {"ok": True}
