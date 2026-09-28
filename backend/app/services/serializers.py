"""Serialisation helpers (PostGIS point -> lat/lon, ORM -> API dicts)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Handover, Lot, Recycler, Transaction


def _point_coords(wkb) -> tuple[float | None, float | None]:
    """Extract (lat, lon) from a PostGIS geography value in a DB-agnostic way."""
    if wkb is None:
        return None, None
    try:
        from geoalchemy2.shape import to_shape

        point = to_shape(wkb)
        return float(point.y), float(point.x)
    except Exception:
        return None, None


def lot_to_dict(db: Session, lot: Lot, include_children: bool = False) -> dict:
    lat, lon = _point_coords(lot.collection_location)
    recycler_name = None
    if lot.recycler_id:
        recycler_name = db.execute(
            select(Recycler.name).where(Recycler.recycler_id == lot.recycler_id)
        ).scalar()
    data = {
        "lot_id": lot.lot_id,
        "client_uuid": lot.client_uuid,
        "collector_id": lot.collector_id,
        "material_category": lot.material_category,
        "material_sub_category": lot.material_sub_category,
        "image_ref": lot.image_ref,
        "declared_weight": lot.declared_weight,
        "verified_weight": lot.verified_weight,
        "estimated_value": lot.estimated_value,
        "recovery_score": lot.recovery_score,
        "mineral_estimate": lot.mineral_estimate,
        "composition_basis": lot.composition_basis,
        "quoted_price": lot.quoted_price,
        "final_price": lot.final_price,
        "recycler_id": lot.recycler_id,
        "recycler_name": recycler_name,
        "collection_district": lot.collection_district,
        "status": lot.status,
        "capture_mode": lot.capture_mode,
        "created_at": lot.created_at,
        "updated_at": lot.updated_at,
        "collection_latitude": lat,
        "collection_longitude": lon,
    }
    if include_children:
        data["handover"] = handover_to_dict(lot.handover) if lot.handover else None
        data["transaction"] = transaction_to_dict(lot.transaction) if lot.transaction else None
    return data


def handover_to_dict(h: Handover) -> dict:
    lat, lon = _point_coords(h.gps_location)
    return {
        "handover_id": h.handover_id,
        "lot_id": h.lot_id,
        "photo_ref": h.photo_ref,
        "gps_latitude": lat,
        "gps_longitude": lon,
        "captured_at": h.captured_at,
        "reference_number": h.reference_number,
        "recycler_confirmation": h.recycler_confirmation,
        "confirmed_at": h.confirmed_at,
        "notes": h.notes,
    }


def transaction_to_dict(t: Transaction) -> dict:
    return {
        "transaction_id": t.transaction_id,
        "lot_id": t.lot_id,
        "collector_id": t.collector_id,
        "recycler_id": t.recycler_id,
        "amount": t.amount,
        "payment_mode": t.payment_mode,
        "payment_status": t.payment_status,
        "paid_at": t.paid_at,
        "created_at": t.created_at,
    }


def recycler_to_dict(recycler: Recycler) -> dict:
    lat, lon = _point_coords(recycler.facility_location)
    return {
        "recycler_id": recycler.recycler_id,
        "name": recycler.name,
        "district": recycler.district,
        "state": recycler.state,
        "materials_accepted": recycler.materials_accepted or [],
        "authorization_status": recycler.authorization_status,
        "registration_number": recycler.registration_number,
        "cpcb_registration_number": recycler.cpcb_registration_number,
        "contact_details": recycler.contact_details,
        "service_area_radius_km": recycler.service_area_radius_km,
        "capacity_kg_per_day": recycler.capacity_kg_per_day,
        "pickup_available": recycler.pickup_available,
        "latitude": lat,
        "longitude": lon,
    }


def collector_to_dict(collector) -> dict:
    lat, lon = _point_coords(collector.operating_location)
    return {
        "collector_id": collector.collector_id,
        "display_name": collector.display_name,
        "preferred_language": collector.preferred_language,
        "phone": collector.phone,
        "district": collector.district,
        "state": collector.state,
        "latitude": lat,
        "longitude": lon,
    }
