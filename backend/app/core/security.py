from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import get_settings


class Role(IntEnum):
    VIEWER = 1
    ANALYST = 2
    ADMIN = 3


class UserContext(BaseModel):
    sub: str
    role: Role
    user_id: str = ""


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(sub: str, role: Role, user_id: str = "") -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": sub,
        "role": role.value,
        "user_id": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> UserContext:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return UserContext(
        sub=payload["sub"],
        role=Role(payload["role"]),
        user_id=payload.get("user_id", ""),
    )


async def get_current_user(token: Annotated[str, Depends(_oauth2_scheme)]) -> UserContext:
    return _decode_token(token)


def require_role(minimum: Role):
    """Return a FastAPI dependency that requires at least `minimum` role."""

    async def _check(user: Annotated[UserContext, Depends(get_current_user)]) -> UserContext:
        if user.role < minimum:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
