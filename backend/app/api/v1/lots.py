"""Lots: create (with instant valuation), list, match, handover, offline sync."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import current_collector
from app.core.constants import CATEGORY_CODES
from app.models import Collector, Handover, Lot, Recycler
from app.schemas import schemas
from app.services import matching, serializers, valuation

router = APIRouter(prefix="/lots", tags=["lots"])


def _reference_number(district: str | None) -> str:
    code = (district or "IND")[:3].upper().ljust(3, "X")
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    return f"KC-{code}-{stamp}-{secrets.token_hex(2).upper()}"


def _create_lot(
    payload: schemas.LotCreate, collector: Collector, db: Session
) -> tuple[Lot, bool]:
    """Idempotent create. Returns (lot, created_now)."""
    if payload.client_uuid:
        existing = (
            db.execute(select(Lot).where(Lot.client_uuid == payload.client_uuid))
            .scalars()
            .first()
        )
        if existing:
            return existing, False

    result = valuation.evaluate_lot(
        db,
        category=payload.material_category,
        weight_kg=payload.declared_weight,
        sub_category=payload.material_sub_category,
        location=payload.district,
    )

    lot = Lot(
        client_uuid=payload.client_uuid,
        collector_id=collector.collector_id,
        material_category=payload.material_category,
        material_sub_category=payload.material_sub_category,
        image_ref=payload.image_ref,
        declared_weight=payload.declared_weight,
        estimated_value=result["estimated_value"],
        recovery_score=result["recovery_score"],
        quoted_price=result["price_used"],
        mineral_estimate=valuation.mineral_estimate_payload(result),
        composition_basis=result["composition_basis"],
        collection_district=payload.district or collector.district,
        status="created",
        capture_mode=payload.capture_mode,
    )
    if payload.latitude is not None and payload.longitude is not None:
        lot.collection_location = WKTElement(
            f"POINT({payload.longitude} {payload.latitude})", srid=4326
        )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot, True


@router.post("", response_model=schemas.LotDetail, status_code=201)
def create_lot(
    payload: schemas.LotCreate,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot, created = _create_lot(payload, collector, db)
    return serializers.lot_to_dict(db, lot, include_children=True)


@router.post("/sync", response_model=list[schemas.LotDetail])
def sync_offline_lots(
    payload: list[schemas.LotSyncItem],
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    """Bulk idempotent upload of lots captured offline (offline-first sync).

    Each item may also carry the recycler match and the handover captured while
    offline, so a fully offline collection cycle reconciles server-side.
    """
    if len(payload) > 200:
        raise HTTPException(status_code=413, detail="Sync batch too large (max 200 lots)")
    out = []
    for item in payload:
        item.capture_mode = "offline"
        lot, created = _create_lot(item, collector, db)
        warning: str | None = None

        if created and item.recycler_id:
            recycler = db.get(Recycler, item.recycler_id)
            if (
                recycler
                and recycler.authorization_status == "authorized"
                and (not recycler.materials_accepted or lot.material_category in recycler.materials_accepted)
            ):
                from app.services import pricing

                offered, _rid, _src = pricing.best_recycler_price(
                    db, lot.material_category, lot.collection_district
                )
                lot.recycler_id = recycler.recycler_id
                lot.status = "matched"
                if offered is not None and offered > 0:
                    lot.quoted_price = offered
                db.commit()
                db.refresh(lot)
            elif recycler:
                warning = (
                    f"Recycler '{recycler.name}' is {recycler.authorization_status}; "
                    "match skipped on sync"
                )

        if created and item.handover and lot.recycler_id is not None:
            handover = Handover(
                lot_id=lot.lot_id,
                reference_number=_reference_number(lot.collection_district),
                captured_at=item.handover.captured_at or item.created_at_client,
            )
            handover.photo_ref = item.handover.photo_ref
            handover.notes = item.handover.notes
            if item.handover.latitude is not None and item.handover.longitude is not None:
                handover.gps_location = WKTElement(
                    f"POINT({item.handover.longitude} {item.handover.latitude})", srid=4326
                )
            db.add(handover)
            lot.status = "handover"
            db.commit()
            db.refresh(lot)

        data = serializers.lot_to_dict(db, lot, include_children=True)
        if warning:
            data["sync_warning"] = warning
        out.append(data)
    return out


@router.get("", response_model=list[schemas.LotDetail])
def list_my_lots(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    q = select(Lot).where(Lot.collector_id == collector.collector_id)
    if status:
        q = q.where(Lot.status == status)
    q = q.order_by(Lot.created_at.desc()).limit(limit)
    lots = db.execute(q).scalars().all()
    return [serializers.lot_to_dict(db, lot, include_children=True) for lot in lots]


@router.get("/{lot_id}", response_model=schemas.LotDetail)
def get_lot(
    lot_id: uuid.UUID,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.collector_id != collector.collector_id:
        raise HTTPException(status_code=404, detail="Lot not found")
    return serializers.lot_to_dict(db, lot, include_children=True)


@router.post("/{lot_id}/valuation", response_model=schemas.ValuationOut)
def revalue_lot(
    lot_id: uuid.UUID,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.collector_id != collector.collector_id:
        raise HTTPException(status_code=404, detail="Lot not found")
    result = valuation.evaluate_lot(
        db,
        category=lot.material_category,
        weight_kg=lot.declared_weight,
        sub_category=lot.material_sub_category,
        location=lot.collection_district,
    )
    return schemas.ValuationOut(**result)


@router.get("/{lot_id}/matches", response_model=list[schemas.RecyclerMatch])
def lot_matches(
    lot_id: uuid.UUID,
    authorized_only: bool = Query(default=True),
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.collector_id != collector.collector_id:
        raise HTTPException(status_code=404, detail="Lot not found")
    lat, lon = serializers._point_coords(lot.collection_location)
    if lat is None:
        lat, lon = serializers._point_coords(collector.operating_location)
    matches = matching.match_recyclers(
        db, lot.material_category, float(lot.declared_weight), lat, lon, authorized_only
    )
    return [_match_to_schema(m) for m in matches]


def _match_to_schema(m: dict) -> schemas.RecyclerMatch:
    base = serializers.recycler_to_dict(m["recycler"])
    base.update(
        {
            "distance_km": m["distance_km"],
            "offered_price": m["offered_price"],
            "rank_score": m["rank_score"],
            "rank_reasons": m["rank_reasons"],
        }
    )
    return schemas.RecyclerMatch(**base)


@router.post("/{lot_id}/match", response_model=schemas.LotDetail)
def match_lot(
    lot_id: uuid.UUID,
    payload: schemas.LotMatchIn,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.collector_id != collector.collector_id:
        raise HTTPException(status_code=404, detail="Lot not found")
    if lot.status in {"verified", "paid"}:
        raise HTTPException(status_code=409, detail=f"Lot already {lot.status}")
    recycler = db.get(Recycler, payload.recycler_id)
    if recycler is None:
        raise HTTPException(status_code=404, detail="Recycler not found")
    if recycler.authorization_status != "authorized":
        raise HTTPException(
            status_code=409,
            detail=f"Recycler is '{recycler.authorization_status}', not authorized for handover",
        )
    if recycler.materials_accepted and lot.material_category not in recycler.materials_accepted:
        raise HTTPException(
            status_code=409, detail="Recycler does not accept this material category"
        )

    from app.services import pricing

    offered, _rid, _src = pricing.best_recycler_price(
        db, lot.material_category, lot.collection_district
    )
    lot.recycler_id = recycler.recycler_id
    lot.status = "matched"
    if offered is not None and offered > 0:
        lot.quoted_price = offered
    db.commit()
    db.refresh(lot)
    return serializers.lot_to_dict(db, lot, include_children=True)


@router.post("/{lot_id}/handover", response_model=schemas.LotDetail)
def create_handover(
    lot_id: uuid.UUID,
    payload: schemas.HandoverCreate,
    collector: Collector = Depends(current_collector),
    db: Session = Depends(get_db),
):
    lot = db.get(Lot, lot_id)
    if lot is None or lot.collector_id != collector.collector_id:
        raise HTTPException(status_code=404, detail="Lot not found")
    if lot.recycler_id is None:
        raise HTTPException(status_code=409, detail="Lot is not matched to a recycler yet")
    if lot.status in {"verified", "paid"}:
        raise HTTPException(status_code=409, detail=f"Lot already {lot.status}")

    handover = lot.handover
    if handover is None:
        handover = Handover(
            lot_id=lot.lot_id,
            reference_number=_reference_number(lot.collection_district),
            captured_at=payload.captured_at or datetime.now(timezone.utc),
        )
        db.add(handover)
    handover.photo_ref = payload.photo_ref or handover.photo_ref
    handover.notes = payload.notes or handover.notes
    if payload.latitude is not None and payload.longitude is not None:
        handover.gps_location = WKTElement(
            f"POINT({payload.longitude} {payload.latitude})", srid=4326
        )
    lot.status = "handover"
    db.commit()
    db.refresh(lot)
    return serializers.lot_to_dict(db, lot, include_children=True)
