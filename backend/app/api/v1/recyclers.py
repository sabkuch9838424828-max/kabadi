"""Recycler directory, onboarding, discovery and matching (public read)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_recycler, get_current_user
from app.core.db import get_db
from app.models import Recycler
from app.schemas import schemas
from app.services import matching, serializers

router = APIRouter(prefix="/recyclers", tags=["recyclers"])


@router.get("", response_model=list[schemas.RecyclerOut])
def list_recyclers(
    category: str | None = Query(default=None),
    authorized_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    q = select(Recycler)
    if authorized_only:
        q = q.where(Recycler.authorization_status == "authorized")
    rows = db.execute(q.order_by(Recycler.name)).scalars().all()
    if category:
        rows = [r for r in rows if not r.materials_accepted or category in r.materials_accepted]
    return [schemas.RecyclerOut(**serializers.recycler_to_dict(r)) for r in rows]


@router.get("/match", response_model=list[schemas.RecyclerMatch])
def match(
    category: str = Query(...),
    weight_kg: float = Query(..., gt=0),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    authorized_only: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Ranked recycler recommendations (public, used by the offline PWA cache)."""
    results = matching.match_recyclers(
        db, category, weight_kg, latitude, longitude, authorized_only
    )
    out = []
    for m in results:
        base = serializers.recycler_to_dict(m["recycler"])
        base.update(
            {
                "distance_km": m["distance_km"],
                "offered_price": m["offered_price"],
                "rank_score": m["rank_score"],
                "rank_reasons": m["rank_reasons"],
            }
        )
        out.append(schemas.RecyclerMatch(**base))
    return out


@router.post("/me", response_model=schemas.RecyclerOut)
def upsert_profile(
    payload: schemas.RecyclerProfileIn,
    recycler: Recycler = Depends(current_recycler),
    db: Session = Depends(get_db),
):
    from geoalchemy2.elements import WKTElement

    recycler.name = payload.name
    recycler.district = payload.district or recycler.district
    recycler.state = payload.state or recycler.state
    recycler.materials_accepted = payload.materials_accepted
    recycler.registration_number = payload.registration_number
    recycler.cpcb_registration_number = payload.cpcb_registration_number
    recycler.contact_details = payload.contact_details
    recycler.service_area_radius_km = payload.service_area_radius_km
    recycler.capacity_kg_per_day = payload.capacity_kg_per_day
    recycler.pickup_available = payload.pickup_available
    if payload.latitude is not None and payload.longitude is not None:
        recycler.facility_location = WKTElement(
            f"POINT({payload.longitude} {payload.latitude})", srid=4326
        )
    db.commit()
    db.refresh(recycler)
    return schemas.RecyclerOut(**serializers.recycler_to_dict(recycler))


@router.get("/me", response_model=schemas.RecyclerOut)
def my_profile(recycler: Recycler = Depends(current_recycler)):
    return schemas.RecyclerOut(**serializers.recycler_to_dict(recycler))
