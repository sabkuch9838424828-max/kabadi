"""Collector onboarding profile + earnings ledger."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_collector, get_current_user
from app.core.db import get_db
from app.models import Collector, Lot, Transaction
from app.schemas import schemas
from app.services import serializers

router = APIRouter(prefix="/collectors", tags=["collectors"])


@router.post("/me", response_model=schemas.CollectorOut)
def upsert_profile(
    payload: schemas.CollectorProfileIn,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    collector.preferred_language = payload.preferred_language
    if payload.display_name is not None:
        collector.display_name = payload.display_name
    if payload.phone is not None:
        collector.phone = payload.phone
    if payload.district is not None:
        collector.district = payload.district
    if payload.state is not None:
        collector.state = payload.state
    if payload.latitude is not None and payload.longitude is not None:
        collector.operating_location = WKTElement(
            f"POINT({payload.longitude} {payload.latitude})", srid=4326
        )
    db.commit()
    db.refresh(collector)
    return schemas.CollectorOut(**serializers.collector_to_dict(collector))


@router.get("/me", response_model=schemas.CollectorOut)
def get_profile(collector: Collector = Depends(current_collector)):
    return schemas.CollectorOut(**serializers.collector_to_dict(collector))


@router.get("/me/ledger", response_model=schemas.LedgerOut)
def ledger(collector: Collector = Depends(current_collector), db: Session = Depends(get_db)):
    transactions = (
        db.execute(
            select(Transaction)
            .where(Transaction.collector_id == collector.collector_id)
            .order_by(Transaction.created_at.desc())
        )
        .scalars()
        .all()
    )
    total_earned = sum(
        (Decimal(t.amount) for t in transactions if t.payment_status == "paid"), Decimal("0")
    )
    pending = sum(
        (Decimal(t.amount) for t in transactions if t.payment_status != "paid"), Decimal("0")
    )
    lifetime_lots = (
        db.execute(
            select(func.count(Lot.lot_id)).where(Lot.collector_id == collector.collector_id)
        ).scalar()
        or 0
    )
    lifetime_kg = (
        db.execute(
            select(func.coalesce(func.sum(Lot.verified_weight), 0)).where(
                Lot.collector_id == collector.collector_id,
                Lot.verified_weight.isnot(None),
            )
        ).scalar()
        or Decimal("0")
    )
    return schemas.LedgerOut(
        total_earned=total_earned,
        pending_dues=pending,
        lifetime_lots=int(lifetime_lots),
        lifetime_kg=Decimal(lifetime_kg),
        transactions=[schemas.TransactionOut.model_validate(t) for t in transactions],
    )
