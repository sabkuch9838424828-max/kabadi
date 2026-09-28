"""FastAPI dependencies: current user + role guards."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models import Collector, Recycler, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise CREDENTIALS_ERROR
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError):
        raise CREDENTIALS_ERROR from None
    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


def require_role(*roles: str):
    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {' or '.join(roles)}",
            )
        return user

    return _guard


def current_collector(
    user: User = Depends(require_role("collector")), db: Session = Depends(get_db)
) -> Collector:
    collector = db.execute(
        select(Collector).where(Collector.user_id == user.user_id)
    ).scalars().first()
    if collector is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collector profile missing. Complete onboarding first (POST /collectors/me).",
        )
    return collector


def current_recycler(
    user: User = Depends(require_role("recycler")), db: Session = Depends(get_db)
) -> Recycler:
    recycler = db.execute(
        select(Recycler).where(Recycler.user_id == user.user_id)
    ).scalars().first()
    if recycler is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recycler profile missing. Complete onboarding first (POST /recyclers/me).",
        )
    return recycler
