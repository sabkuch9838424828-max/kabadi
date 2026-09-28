"""Recycler console operations: incoming lots, verify weight, confirm, history."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_recycler
from app.core.db import get_db
from app.models import Handover, Lot, Recycler, Transaction
from app.schemas import schemas
from app.services import serializers, valuation

router = APIRouter(prefix="/recycler", tags=["recycler-console"])


@router.get("/lots", response_model=list[schemas.LotDetail])
def incoming_lots(
    status: str | None = Query(default=None),
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    q = select(Lot).where(Lot.recycler_id == recycler.recycler_id)
    if status:
        q = q.where(Lot.status == status)
    lots = db.execute(q.order_by(Lot.created_at.desc())).scalars().all()
    return [serializers.lot_to_dict(db, lot, include_children=True) for lot in lots]


@router.post("/lots/{lot_id}/verify", response_model=schemas.LotDetail)
def verify_weight(
    lot_id: uuid.UUID,
    payload: schemas.VerifyWeightIn,
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    """Verify the physically weighed mass and settle payment on the verified weight.

    Trust layer (documentation Pillar 2): final payment is computed ONLY on the
    verified weight — declared vs verified are tracked separately.
    """
    lot = db.get(Lot, lot_id)
    if lot is None or lot.recycler_id != recycler.recycler_id:
        raise HTTPException(status_code=404, detail="Lot not assigned to you")
    if lot.handover is None:
        raise HTTPException(status_code=409, detail="Collector has not recorded a handover yet")
    if lot.status in {"verified", "paid"}:
        raise HTTPException(status_code=409, detail=f"Lot already {lot.status}")

    verified = Decimal(str(payload.verified_weight))
    if verified <= 0:
        raise HTTPException(status_code=422, detail="Verified weight must be greater than zero")
    # quoted_price is a per-kg rate (see pricing.best_recycler_price and seed);
    # fall back to the estimate's implied unit rate if no match price exists yet.
    unit_price = Decimal(lot.quoted_price or 0)
    if unit_price <= 0 and lot.declared_weight:
        unit_price = Decimal(lot.estimated_value or 0) / Decimal(lot.declared_weight)
    if unit_price <= 0:
        raise HTTPException(status_code=409, detail="No agreed price on this lot")
    final_price = (unit_price * verified).quantize(Decimal("0.01"))

    lot.verified_weight = verified
    lot.final_price = final_price
    if payload.notes:
        lot.handover.notes = payload.notes

    lot.handover.recycler_confirmation = True
    lot.handover.confirmed_at = datetime.now(timezone.utc)

    anomaly = valuation.flag_weight_anomaly(db, lot.lot_id, lot.declared_weight, verified)

    txn = lot.transaction
    if txn is None:
        txn = Transaction(
            lot_id=lot.lot_id,
            collector_id=lot.collector_id,
            recycler_id=recycler.recycler_id,
            amount=final_price,
            payment_mode=payload.payment_mode,
            payment_status="pending",
        )
        db.add(txn)
    else:
        txn.amount = final_price
        txn.payment_mode = payload.payment_mode

    lot.status = "verified"
    db.commit()
    db.refresh(lot)
    data = serializers.lot_to_dict(db, lot, include_children=True)
    data["weight_anomaly"] = anomaly
    return data


@router.post("/lots/{lot_id}/pay", response_model=schemas.LotDetail)
def mark_paid(
    lot_id: uuid.UUID,
    payment_mode: str = Query(default="cash", pattern="^(cash|upi)$"),
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.recycler_id != recycler.recycler_id:
        raise HTTPException(status_code=404, detail="Lot not assigned to you")
    if lot.transaction is None:
        raise HTTPException(status_code=409, detail="Lot has not been verified yet")
    txn = lot.transaction
    txn.payment_mode = payment_mode
    txn.payment_status = "paid"
    txn.paid_at = datetime.now(timezone.utc)
    lot.status = "paid"
    db.commit()
    db.refresh(lot)
    return serializers.lot_to_dict(db, lot, include_children=True)


@router.post("/lots/{lot_id}/decline", response_model=schemas.LotDetail)
def decline_lot(
    lot_id: uuid.UUID,
    payload: schemas.DeclineIn,
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.recycler_id != recycler.recycler_id:
        raise HTTPException(status_code=404, detail="Lot not assigned to you")
    if lot.status in {"verified", "paid"}:
        raise HTTPException(status_code=409, detail="Cannot decline a settled lot")
    lot.status = "declined"
    if lot.handover:
        lot.handover.notes = payload.reason
    db.commit()
    db.refresh(lot)
    return serializers.lot_to_dict(db, lot, include_children=True)


@router.get("/handovers", response_model=list[schemas.HandoverOut])
def handovers(
    recycler: Recycler = Depends(current_recycler), db: Session = Depends(get_db)
):
    lots = (
        db.execute(select(Lot.lot_id).where(Lot.recycler_id == recycler.recycler_id))
        .scalars()
        .all()
    )
    if not lots:
        return []
    rows = (
        db.execute(
            select(Handover)
            .where(Handover.lot_id.in_(lots))
            .order_by(Handover.captured_at.desc())
        )
        .scalars()
        .all()
    )
    return [schemas.HandoverOut(**serializers.handover_to_dict(h)) for h in rows]


@router.get("/history", response_model=list[schemas.LotDetail])
def history(
    limit: int = Query(default=100, ge=1, le=500),
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    lots = (
        db.execute(
            select(Lot)
            .where(Lot.recycler_id == recycler.recycler_id, Lot.status.in_(["verified", "paid", "declined"]))
            .order_by(Lot.updated_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [serializers.lot_to_dict(db, lot, include_children=True) for lot in lots]
