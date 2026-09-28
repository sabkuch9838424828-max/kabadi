"""Analytics aggregation for the Admin / Ministry dashboard.

All mineral-recovery and CO2 figures are visible *estimates* derived from the
stoichiometric engine, and the response carries that disclaimer explicitly so
the dashboard can display it (documentation section 5.C.3 + Jury Q&A honesty).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Collector, FraudFlag, Lot, Recycler, Transaction
from app.ml.stoichiometry import CRITICAL_ELEMENTS

DISCLAIMER = (
    "Critical-mineral recovery and CO2-offset figures are estimates derived from "
    "published stoichiometric composition ratios applied to verified batch weights. "
    "They are not laboratory assay measurements."
)


def _minerals_from_lots(db: Session, include_verified_only: bool = True) -> dict[str, dict]:
    q = select(Lot).where(Lot.mineral_estimate.isnot(None))
    if include_verified_only:
        q = q.where(Lot.verified_weight.isnot(None))
    lots = db.execute(q).scalars().all()

    totals: dict[str, dict] = {}
    for lot in lots:
        weight = Decimal(lot.verified_weight or lot.declared_weight or 0)
        declared = Decimal(lot.declared_weight or 0)
        scale = (weight / declared) if declared > 0 else Decimal("1")
        est = (lot.mineral_estimate or {}).get("minerals", {}) if lot.mineral_estimate else {}
        for element, m in est.items():
            bucket = totals.setdefault(
                element,
                {
                    "element": element,
                    "kg": Decimal("0"),
                    "value_inr": Decimal("0"),
                    "is_critical": element in CRITICAL_ELEMENTS or bool(m.get("is_critical")),
                },
            )
            bucket["kg"] += Decimal(str(m.get("kg_mid", 0))) * scale
            bucket["value_inr"] += Decimal(str(m.get("value_inr", 0))) * scale
    return totals


def build_analytics(db: Session) -> dict:
    lots = db.execute(select(Lot)).scalars().all()

    total_lots = len(lots)
    total_declared = sum((Decimal(l.declared_weight or 0) for l in lots), Decimal("0"))
    verified_lots = [l for l in lots if l.verified_weight is not None]
    total_verified = sum((Decimal(l.verified_weight or 0) for l in verified_lots), Decimal("0"))

    active_collectors = (
        db.execute(select(func.count(func.distinct(Lot.collector_id)))).scalar() or 0
    )
    active_recyclers = (
        db.execute(
            select(func.count(func.distinct(Lot.recycler_id))).where(Lot.recycler_id.isnot(None))
        ).scalar()
        or 0
    )
    authorized_recyclers = (
        db.execute(
            select(func.count(Recycler.recycler_id)).where(
                Recycler.authorization_status == "authorized"
            )
        ).scalar()
        or 0
    )

    minerals = _minerals_from_lots(db)
    critical = sorted(
        (m for m in minerals.values() if m["is_critical"]),
        key=lambda m: m["kg"],
        reverse=True,
    )

    co2_total = Decimal("0")
    for lot in verified_lots:
        est = lot.mineral_estimate or {}
        co2_total += Decimal(str(est.get("co2_offset_kg", 0)))

    # district heatmap from collection location
    district_rows = db.execute(
        select(
            Lot.collection_district,
            func.count(Lot.lot_id),
            func.coalesce(func.sum(Lot.verified_weight), 0),
        )
        .where(Lot.collection_district.isnot(None))
        .group_by(Lot.collection_district)
        .order_by(func.count(Lot.lot_id).desc())
    ).all()

    category_rows = db.execute(
        select(
            Lot.material_category,
            func.count(Lot.lot_id),
            func.coalesce(func.sum(Lot.verified_weight), 0),
            func.coalesce(func.avg(Lot.recovery_score), 0),
        )
        .group_by(Lot.material_category)
        .order_by(func.count(Lot.lot_id).desc())
    ).all()

    anomalies = db.execute(select(func.count(FraudFlag.id))).scalar() or 0

    scores = [Decimal(l.recovery_score) for l in lots if l.recovery_score is not None]
    avg_score = (sum(scores) / len(scores)).quantize(Decimal("0.01")) if scores else None

    diff_pct = None
    if total_declared > 0:
        diff_pct = float((total_verified - total_declared) / total_declared * 100)

    return {
        "total_lots": total_lots,
        "total_declared_kg": total_declared.quantize(Decimal("0.001")),
        "total_verified_kg": total_verified.quantize(Decimal("0.001")),
        "material_collected_kg": total_verified.quantize(Decimal("0.001")),
        "active_collectors": int(active_collectors),
        "active_recyclers": int(active_recyclers),
        "authorized_recyclers": int(authorized_recyclers),
        "critical_minerals_recovered": [
            {
                "element": m["element"],
                "kg": float(m["kg"].quantize(Decimal("0.001"))),
                "estimated_value_inr": float(m["value_inr"].quantize(Decimal("0.01"))),
                "is_critical": m["is_critical"],
            }
            for m in critical
        ],
        "co2_offset_kg": co2_total.quantize(Decimal("0.001")),
        "recovery_score_avg": avg_score,
        "district_heatmap": [
            {
                "district": d,
                "lots": int(c),
                "verified_kg": float(Decimal(v or 0)),
            }
            for d, c, v in district_rows
        ],
        "category_breakdown": [
            {
                "material_category": cat,
                "lots": int(c),
                "verified_kg": float(Decimal(v or 0)),
                "avg_recovery_score": round(float(avg or 0), 2),
            }
            for cat, c, v, avg in category_rows
        ],
        "declared_vs_verified": {
            "declared_kg": float(total_declared),
            "verified_kg": float(total_verified),
            "difference_pct": round(diff_pct, 2) if diff_pct is not None else None,
            "verified_lots": len(verified_lots),
        },
        "price_anomalies": int(anomalies),
        "is_estimate_disclaimer": DISCLAIMER,
    }
