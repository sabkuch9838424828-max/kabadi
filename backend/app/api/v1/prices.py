"""Public price board (voice-friendly) + recycler price management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_recycler, get_current_user
from app.core.db import get_db
from app.models import MaterialPrice, PriceHistory, Recycler
from app.schemas import schemas
from app.services import pricing, valuation

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/board", response_model=list[schemas.PriceBoardEntry])
def board(
    location: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    """Current rates by category/location with simple trend arrows.

    Public (no auth) so the offline PWA can cache it, but every row is marked
    `is_estimate` because recycler quotes are indicative, not settled trades.
    """
    return pricing.price_board(db, location)


@router.get("/history/{category}", response_model=schemas.TrendPoint)
def history(
    category: str,
    location: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    q = select(PriceHistory).where(PriceHistory.material_category == category)
    if location:
        q = q.where(PriceHistory.location == location)
    rows = db.execute(q.order_by(PriceHistory.recorded_at.asc())).scalars().all()
    return schemas.TrendPoint(
        material_category=category,
        points=[
            {"price": r.price, "recorded_at": r.recorded_at.isoformat(), "location": r.location}
            for r in rows
        ],
    )


@router.post("/anomaly-check", tags=["prices"])
def anomaly_check(
    payload: schemas.PriceCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return valuation.check_price_anomaly(
        db, payload.material_category, payload.buying_price, payload.location
    )


@router.post("", response_model=schemas.PriceOut, status_code=201)
def publish_rate(
    payload: schemas.PriceCreate,
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    """A recycler publishes/updates the rate they will pay for a category."""
    if payload.location in ("", None):
        payload.location = recycler.district or "IN"

    anomaly = valuation.check_price_anomaly(
        db, payload.material_category, payload.buying_price, payload.location
    )
    if anomaly["is_anomaly"] and anomaly["severity"] in {"medium", "high"}:
        # Prevent the historical baseline from being poisoned by off-market
        # quotes: reject and do NOT persist into the price series.
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Rate rejected by anomaly detector — please verify.",
                "anomaly": anomaly,
            },
        )

    row = MaterialPrice(
        material_category=payload.material_category,
        sub_category=payload.sub_category,
        location=payload.location,
        buying_price=payload.buying_price,
        unit=payload.unit,
        source="recycler",
        is_benchmark=False,
        recycler_id=recycler.recycler_id,
    )
    db.add(row)
    db.add(
        PriceHistory(
            material_category=payload.material_category,
            location=payload.location,
            price=payload.buying_price,
        )
    )
    db.commit()
    db.refresh(row)
    out = schemas.PriceOut.model_validate(row)
    return out


@router.get("/mine", response_model=list[schemas.PriceOut])
def my_rates(
    recycler: Recycler = Depends(current_recycler), db: Session = Depends(get_db)
):
    rows = (
        db.execute(
            select(MaterialPrice)
            .where(MaterialPrice.recycler_id == recycler.recycler_id)
            .order_by(MaterialPrice.recorded_at.desc())
        )
        .scalars()
        .all()
    )
    return [schemas.PriceOut.model_validate(r) for r in rows]
