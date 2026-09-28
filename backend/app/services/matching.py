"""Recycler matching / recommendation engine.

Ranks recyclers on the documented criteria (section 5.D.4):
    location distance  +  offered rate  +  capacity  +  authorization status
    +  material acceptance  +  pickup availability
"""
from __future__ import annotations

import math
import uuid
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models import MaterialPrice, Recycler
from app.services import pricing

EARTH_RADIUS_KM = 6371.0088

W_DISTANCE = 0.35
W_PRICE = 0.30
W_AUTH = 0.15
W_CAPACITY = 0.10
W_ACCEPT = 0.10

AUTH_SCORE = {"authorized": 1.0, "pending": 0.45, "unverified": 0.15, "suspended": 0.0}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _coords(row: Recycler) -> tuple[float | None, float | None]:
    # lat/lon extracted in the query via ST_Y/ST_X aliases; see _load_recyclers
    return getattr(row, "_lat", None), getattr(row, "_lon", None)


def _load_recyclers(
    db: Session,
    category: str,
    authorized_only: bool,
    lat: float | None,
    lon: float | None,
) -> list[dict]:
    # geography columns must be cast to geometry before ST_X/ST_Y
    lat_col = func.ST_Y(cast(Recycler.facility_location, Geometry)).label("lat")
    lon_col = func.ST_X(cast(Recycler.facility_location, Geometry)).label("lon")
    rows = db.execute(select(Recycler, lat_col, lon_col)).all()

    prices = {
        r.recycler_id: Decimal(r.buying_price)
        for r in db.execute(
            select(MaterialPrice).where(
                MaterialPrice.material_category == category,
                MaterialPrice.is_benchmark.is_(False),
                MaterialPrice.recycler_id.isnot(None),
            )
        ).scalars()
    }
    benchmark = pricing.benchmark_price(db, category)
    bench_val = Decimal(benchmark.buying_price) if benchmark else None

    result: list[dict] = []
    for recycler, rlat, rlon in rows:
        if authorized_only and recycler.authorization_status != "authorized":
            continue
        distance = None
        if lat is not None and lon is not None and rlat is not None and rlon is not None:
            distance = haversine_km(lat, lon, float(rlat), float(rlon))
        accepts = not recycler.materials_accepted or category in (recycler.materials_accepted or [])
        if not accepts:
            continue
        result.append(
            {
                "recycler": recycler,
                "lat": float(rlat) if rlat is not None else None,
                "lon": float(rlon) if rlon is not None else None,
                "distance_km": distance,
                "offered_price": prices.get(recycler.recycler_id),
                "benchmark": bench_val,
            }
        )
    return result


def match_recyclers(
    db: Session,
    category: str,
    weight_kg: Decimal,
    lat: float | None = None,
    lon: float | None = None,
    authorized_only: bool = True,
    limit: int = 10,
) -> list[dict]:
    candidates = _load_recyclers(db, category, authorized_only, lat, lon)
    if not candidates:
        return []

    # Normalisers
    max_radius = max(
        [c["recycler"].service_area_radius_km or Decimal("25") for c in candidates],
        default=Decimal("25"),
    )
    max_distance_seen = max(
        [c["distance_km"] for c in candidates if c["distance_km"] is not None] or [1.0]
    )
    max_price = max(
        [c["offered_price"] for c in candidates if c["offered_price"] is not None]
        or [Decimal("1")]
    )

    out: list[dict] = []
    for c in candidates:
        recycler: Recycler = c["recycler"]
        reasons: list[str] = []

        # --- distance component -------------------------------------------
        radius = float(recycler.service_area_radius_km or 25)
        if c["distance_km"] is not None:
            within = c["distance_km"] <= radius
            distance_score = max(0.0, 1.0 - (c["distance_km"] / max(max_distance_seen, radius, 1.0)))
            reasons.append(
                f"{c['distance_km']:.1f} km away"
                + (f" (within {radius:.0f} km service area)" if within else f" (outside {radius:.0f} km service area)")
            )
            if not within:
                distance_score *= 0.25
        else:
            distance_score = 0.4
            reasons.append("location not shared — distance not scored")

        # --- price component ----------------------------------------------
        offered = c["offered_price"]
        if offered is not None and max_price > 0:
            price_score = float(offered / max_price)
            reasons.append(f"offers INR {offered}/kg")
            if c["benchmark"] is not None and offered >= c["benchmark"]:
                reasons.append("at or above MSP benchmark")
        else:
            price_score = 0.0
            reasons.append("no rate published for this category")

        # --- authorization -------------------------------------------------
        auth_score = AUTH_SCORE.get(recycler.authorization_status, 0.0)
        reasons.append(f"CPCB status: {recycler.authorization_status}")

        # --- capacity vs batch size ---------------------------------------
        cap = float(recycler.capacity_kg_per_day or 0)
        if cap > 0:
            capacity_score = min(1.0, cap / max(float(weight_kg), 1.0))
            reasons.append(f"capacity {cap:.0f} kg/day")
        else:
            capacity_score = 0.5

        accepts_all = not recycler.materials_accepted
        accept_score = 1.0 if accepts_all else (
            1.0 if category in recycler.materials_accepted else 0.0
        )
        if accepts_all:
            reasons.append("accepts all categories")
        if recycler.pickup_available:
            reasons.append("doorstep pickup available")

        rank = (
            W_DISTANCE * distance_score
            + W_PRICE * price_score
            + W_AUTH * auth_score
            + W_CAPACITY * capacity_score
            + W_ACCEPT * accept_score
        )
        # Hard demotion for non-authorized when the caller allowed them through.
        if recycler.authorization_status != "authorized":
            rank *= 0.5

        out.append(
            {
                "recycler": recycler,
                "lat": c["lat"],
                "lon": c["lon"],
                "distance_km": round(c["distance_km"], 2) if c["distance_km"] is not None else None,
                "offered_price": offered,
                "rank_score": round(rank * 100, 2),
                "rank_reasons": reasons,
            }
        )

    out.sort(key=lambda r: r["rank_score"], reverse=True)
    return out[:limit]
