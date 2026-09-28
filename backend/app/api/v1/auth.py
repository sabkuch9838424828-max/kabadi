"""Authentication: register, OAuth2 token, current profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Collector, Recycler, User
from app.schemas import schemas
from app.services import serializers

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> schemas.Token:
    existing = db.execute(select(User).where(User.email == payload.email)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        phone=payload.phone,
    )
    db.add(user)
    db.flush()

    # Create the matching profile shell so onboarding can PATCH it.
    if user.role == "collector":
        db.add(Collector(user_id=user.user_id, display_name=user.full_name, phone=user.phone))
    elif user.role == "recycler":
        db.add(Recycler(user_id=user.user_id, name=user.full_name, authorization_status="unverified"))

    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.user_id), user.role)
    return schemas.Token(
        access_token=token, role=user.role, user_id=user.user_id, full_name=user.full_name
    )


@router.post("/token", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> schemas.Token:
    """OAuth2 password flow — username is the email address."""
    user = db.execute(select(User).where(User.email == form_data.username)).scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    token = create_access_token(str(user.user_id), user.role)
    return schemas.Token(
        access_token=token, role=user.role, user_id=user.user_id, full_name=user.full_name
    )


@router.get("/me", response_model=schemas.MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> schemas.MeOut:
    collector_out = None
    recycler_out = None
    if user.role == "collector":
        collector = db.execute(
            select(Collector).where(Collector.user_id == user.user_id)
        ).scalars().first()
        if collector:
            collector_out = schemas.CollectorOut(**serializers.collector_to_dict(collector))
    elif user.role == "recycler":
        recycler = db.execute(
            select(Recycler).where(Recycler.user_id == user.user_id)
        ).scalars().first()
        if recycler:
            recycler_out = schemas.RecyclerOut(**serializers.recycler_to_dict(recycler))
    return schemas.MeOut(
        user=schemas.UserOut.model_validate(user),
        collector=collector_out,
        recycler=recycler_out,
    )
