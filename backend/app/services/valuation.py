"""Valuation service: composition lookup + pricing + scoring + anomaly check."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import anomaly, stoichiometry
from app.models import FraudFlag, MaterialComposition, PriceHistory
from app.services import pricing


def compositions_for(db: Session, category: str, sub_category: str | None = None) -> list[dict]:
    """Composition rows for a category; battery chemistry refines the ratio set."""
    rows = (
        db.execute(
            select(MaterialComposition).where(MaterialComposition.material_category == category)
        )
        .scalars()
        .all()
    )
    if not rows:
        return []
    return [
        {
            "element": r.element,
            "ratio_low": r.ratio_low,
            "ratio_high": r.ratio_high,
            "ratio_mid": r.ratio_mid,
            "is_critical": r.is_critical,
        }
        for r in rows
    ]


def co2_factor_for(db: Session, category: str) -> Decimal:
    row = (
        db.execute(
            select(MaterialComposition.co2_factor)
            .where(MaterialComposition.material_category == category)
            .limit(1)
        )
        .scalars()
        .first()
    )
    return Decimal(row) if row is not None else Decimal("0")


def evaluate_lot(
    db: Session,
    category: str,
    weight_kg: Decimal,
    sub_category: str | None = None,
    location: str | None = None,
    allow_zero_price: bool = True,
) -> dict:
    price, source, benchmark = pricing.effective_price(db, category, location)
    if price <= 0 and not allow_zero_price:
        raise ValueError(f"No price available for category '{category}'")

    compositions = compositions_for(db, category, sub_category)
    result = stoichiometry.evaluate(
        category=category,
        weight_kg=weight_kg,
        compositions=compositions,
        price=price,
        price_source=source,
        co2_factor=co2_factor_for(db, category),
    )
    result["benchmark_price"] = benchmark
    result["composition_basis"] = {
        "method": "published_stoichiometric_ratios",
        "ratios": {m["element"]: [m["ratio_low"], m["ratio_high"]] for m in result["minerals"].values()},
        "note": stoichiometry.DISCLAIMER,
    }
    return result


def check_price_anomaly(
    db: Session, category: str, quoted: Decimal, location: str | None = None
) -> dict:
    location = pricing.location_fallback(db, location, category)
    q = select(PriceHistory.price).where(PriceHistory.material_category == category)
    if location:
        q = q.where(PriceHistory.location == location)
    history = [float(p) for p in db.execute(q).scalars().all()]
    if len(history) < 4 and location:
        # national series fallback so the detector still has a baseline
        history = [
            float(p)
            for p in db.execute(
                select(PriceHistory.price).where(PriceHistory.material_category == category)
            )
            .scalars()
            .all()
        ]
    res = anomaly.detect_price_anomaly(float(quoted), history)
    out = {
        "is_anomaly": res.is_anomaly,
        "score": res.score,
        "severity": res.severity,
        "method": res.method,
        "expected_range": list(res.expected_range) if res.expected_range else None,
        "detail": res.detail,
    }
    if res.is_anomaly:
        db.add(
            FraudFlag(
                kind="price_anomaly",
                severity=res.severity,
                detail={"material_category": category, "quoted": float(quoted), **out},
            )
        )
        db.commit()
    return out


def reconcile_price_history(db: Session, category: str, location: str | None = None) -> int:
    """Remove gross outliers (>=3x the median) from the historical series.

    Guards the anomaly detector against its own baseline being poisoned by a
    quote that was persisted before the guard existed.
    """
    from sqlalchemy import delete, func

    from app.models import PriceHistory as PH

    q = select(PH.price).where(PH.material_category == category)
    if location:
        q = q.where(PH.location == location)
    values = [float(v) for v in db.execute(q).scalars().all()]
    if len(values) < 4:
        return 0
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    if median <= 0:
        return 0
    cutoff = median * 3
    dq = delete(PH).where(PH.material_category == category, PH.price > cutoff)
    if location:
        dq = dq.where(PH.location == location)
    result = db.execute(dq)
    db.commit()
    return result.rowcount or 0


def flag_weight_anomaly(db: Session, lot_id, declared: Decimal, verified: Decimal) -> dict:
    res = anomaly.detect_weight_anomaly(float(declared), float(verified))
    if res.is_anomaly:
        db.add(
            FraudFlag(
                lot_id=lot_id,
                kind="weight_deviation",
                severity=res.severity,
                detail={
                    "declared_weight": float(declared),
                    "verified_weight": float(verified),
                    "deviation_pct": res.score,
                    "detail": res.detail,
                },
            )
        )
        db.commit()
    return {
        "is_anomaly": res.is_anomaly,
        "score": res.score,
        "severity": res.severity,
        "detail": res.detail,
    }


def json_safe(value):
    """Recursively convert Decimal/date objects into JSON-serialisable values.

    Needed because mineral_estimate is stored in a JSONB column and Decimal is
    not JSON-serialisable by the stdlib encoder.
    """
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def mineral_estimate_payload(result: dict) -> dict:
    return json_safe(
        {
            "minerals": result["minerals"],
            "co2_offset_kg": result["co2_offset_kg"],
            "price_source": result["price_source"],
            "benchmark_price": result.get("benchmark_price"),
            "estimated_value": result["estimated_value"],
            "recovery_score": result["recovery_score"],
            "is_estimate": True,
            "disclaimer": result["disclaimer"],
        }
    )
