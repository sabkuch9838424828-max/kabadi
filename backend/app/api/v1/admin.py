"""Admin / Ministry dashboard endpoints: recycler authorization, MSP board,
analytics, audit trail."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.db import get_db
from app.models import AuditLog, FraudFlag, MaterialPrice, PriceHistory, Recycler, User
from app.schemas import schemas
from app.services import analytics, serializers

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(
    db: Session, user: User, action: str, entity: str | None = None,
    entity_id: str | None = None, detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=user.user_id,
            actor_role=user.role,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
        )
    )


@router.get("/recyclers", response_model=list[schemas.RecyclerOut])
def all_recyclers(
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    q = select(Recycler)
    if status_filter:
        q = q.where(Recycler.authorization_status == status_filter)
    rows = db.execute(q.order_by(Recycler.name)).scalars().all()
    return [schemas.RecyclerOut(**serializers.recycler_to_dict(r)) for r in rows]


@router.patch("/recyclers/{recycler_id}/authorization", response_model=schemas.RecyclerOut)
def update_authorization(
    recycler_id: uuid.UUID,
    payload: schemas.AuthorizationUpdate,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """CPCB registration verify / approve / suspend."""
    recycler = db.get(Recycler, recycler_id)
    if recycler is None:
        raise HTTPException(status_code=404, detail="Recycler not found")
    if payload.authorization_status == "authorized" and not (
        recycler.cpcb_registration_number or recycler.registration_number
    ):
        raise HTTPException(
            status_code=422,
            detail="Cannot authorize without a CPCB / registration number on file",
        )
    previous = recycler.authorization_status
    recycler.authorization_status = payload.authorization_status
    _audit(
        db,
        user,
        "recycler_authorization_update",
        entity="recycler",
        entity_id=str(recycler.recycler_id),
        detail={
            "from": previous,
            "to": payload.authorization_status,
            "note": payload.note,
        },
    )
    db.commit()
    db.refresh(recycler)
    return schemas.RecyclerOut(**serializers.recycler_to_dict(recycler))


@router.post("/prices/benchmark", response_model=schemas.PriceOut, status_code=201)
def set_benchmark(
    payload: schemas.BenchmarkCreate,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Set the Ministry of Mines MSP benchmark price for a category/location."""
    row = MaterialPrice(
        material_category=payload.material_category,
        sub_category=payload.sub_category,
        location=payload.location or "IN",
        buying_price=payload.buying_price,
        unit=payload.unit,
        source="msp_benchmark",
        is_benchmark=True,
        recycler_id=None,
    )
    db.add(row)
    db.add(
        PriceHistory(
            material_category=payload.material_category,
            location=payload.location or "IN",
            price=payload.buying_price,
        )
    )
    _audit(
        db,
        user,
        "msp_benchmark_set",
        entity="material_price",
        detail={
            "material_category": payload.material_category,
            "location": payload.location,
            "price": str(payload.buying_price),
        },
    )
    db.commit()
    db.refresh(row)
    return schemas.PriceOut.model_validate(row)


@router.get("/prices", response_model=list[schemas.PriceOut])
def all_prices(
    user: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    rows = (
        db.execute(select(MaterialPrice).order_by(MaterialPrice.recorded_at.desc()).limit(300))
        .scalars()
        .all()
    )
    return [schemas.PriceOut.model_validate(r) for r in rows]


@router.get("/analytics", response_model=schemas.AnalyticsOut)
def get_analytics(
    user: User = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    return schemas.AnalyticsOut(**analytics.build_analytics(db))


@router.get("/fraud-flags")
def fraud_flags(
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(select(FraudFlag).order_by(FraudFlag.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "lot_id": str(r.lot_id) if r.lot_id else None,
            "kind": r.kind,
            "severity": r.severity,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/audit-log")
def audit_log(
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "actor_role": r.actor_role,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
