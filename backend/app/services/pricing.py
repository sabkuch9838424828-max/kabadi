"""Price discovery service.

Blends two official-ish sources, exactly as the documentation requires
(Innovation Pillar 4 — "Built directly on Ministry of Mines MSP benchmark price
board / CPCB authorized recycler list"):

  * MSP benchmark rows      (is_benchmark=True, source='msp_benchmark')
  * Recycler-offered rates  (source='recycler')

The collector is quoted the best *authorized* recycler rate (falling back to the
MSP benchmark) and the board exposes both, with a simple trend arrow computed
from PriceHistory.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MaterialPrice, PriceHistory, Recycler

TREND_FLAT_BAND_PCT = 1.0

# A recycler quote more than this multiple of the benchmark is treated as a
# data error / bad actor and excluded from the board and from collector quotes.
MAX_QUOTE_MULTIPLE_OF_BENCHMARK = Decimal("3")


def benchmark_price(db: Session, category: str, location: str | None = None) -> MaterialPrice | None:
    q = (
        select(MaterialPrice)
        .where(
            MaterialPrice.material_category == category,
            MaterialPrice.is_benchmark.is_(True),
        )
        .order_by(MaterialPrice.recorded_at.desc())
    )
    if location:
        q = q.where(MaterialPrice.location == location)
    row = db.execute(q).scalars().first()
    if row is None and location:
        # national fallback
        row = (
            db.execute(
                select(MaterialPrice)
                .where(
                    MaterialPrice.material_category == category,
                    MaterialPrice.is_benchmark.is_(True),
                )
                .order_by(MaterialPrice.recorded_at.desc())
            )
            .scalars()
            .first()
        )
    return row


def _sanity_ceiling(db: Session, category: str, location: str | None) -> Decimal | None:
    """Upper bound for a legitimate quote: 3x the MSP benchmark.

    Protects the collector board and the matching engine from a corrupted or
    maliciously-published rate that slipped past the ingestion-time detector.
    """
    bench = benchmark_price(db, category, location)
    if bench is None:
        return None
    return Decimal(bench.buying_price) * MAX_QUOTE_MULTIPLE_OF_BENCHMARK


def best_recycler_price(
    db: Session, category: str, location: str | None = None, authorized_only: bool = True
) -> tuple[Decimal | None, uuid.UUID | None, str]:
    """Returns (price, recycler_id, source_label) for the best offered rate."""
    ceiling = _sanity_ceiling(db, category, location)
    q = (
        select(MaterialPrice, Recycler)
        .join(Recycler, MaterialPrice.recycler_id == Recycler.recycler_id)
        .where(
            MaterialPrice.material_category == category,
            MaterialPrice.is_benchmark.is_(False),
        )
        .order_by(MaterialPrice.buying_price.desc())
    )
    if authorized_only:
        q = q.where(Recycler.authorization_status == "authorized")
    if location:
        q = q.where(MaterialPrice.location == location)
    if ceiling is not None:
        q = q.where(MaterialPrice.buying_price <= ceiling)
    row = db.execute(q).first()
    if row is None and location:
        q2 = (
            select(MaterialPrice, Recycler)
            .join(Recycler, MaterialPrice.recycler_id == Recycler.recycler_id)
            .where(
                MaterialPrice.material_category == category,
                MaterialPrice.is_benchmark.is_(False),
            )
            .order_by(MaterialPrice.buying_price.desc())
        )
        if authorized_only:
            q2 = q2.where(Recycler.authorization_status == "authorized")
        if ceiling is not None:
            q2 = q2.where(MaterialPrice.buying_price <= ceiling)
        row = db.execute(q2).first()
    if row is None:
        return None, None, "none"
    price_row, recycler = row
    return Decimal(price_row.buying_price), price_row.recycler_id, "authorized_recycler"


def effective_price(
    db: Session, category: str, location: str | None = None
) -> tuple[Decimal, str, Decimal | None]:
    """Best available price for a collector quote.

    Returns (price, source, benchmark_reference).
    """
    best, recycler_id, source = best_recycler_price(db, category, location)
    bench = benchmark_price(db, category, location)
    bench_val = Decimal(bench.buying_price) if bench else None

    if best is None:
        if bench_val is not None:
            return bench_val, "msp_benchmark", bench_val
        return Decimal("0"), "unavailable", None

    if bench_val is not None and best < bench_val:
        # Benchmark acts as a floor so collectors are never underpaid.
        return bench_val, "msp_benchmark_floor", bench_val
    return best, source, bench_val


def location_fallback(db: Session, location: str | None, category: str) -> str | None:
    """Return `location` if it has any benchmark/recycler prices, else None.

    Allows callers to fall back to national rates instead of failing when a
    collector's district has no published board yet.
    """
    if not location:
        return None
    found = (
        db.execute(
            select(MaterialPrice.price_id)
            .where(
                MaterialPrice.material_category == category,
                MaterialPrice.location == location,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    return location if found else None


def _trend(db: Session, category: str, location: str | None) -> tuple[str, float]:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    q = (
        select(PriceHistory.price, PriceHistory.recorded_at)
        .where(PriceHistory.material_category == category, PriceHistory.recorded_at >= since)
        .order_by(PriceHistory.recorded_at.asc())
    )
    if location:
        q = q.where(PriceHistory.location == location)
    rows = db.execute(q).all()
    if len(rows) < 2:
        return "flat", 0.0
    first, last = float(rows[0][0]), float(rows[-1][0])
    if first <= 0:
        return "flat", 0.0
    pct = (last - first) / first * 100.0
    if pct > TREND_FLAT_BAND_PCT:
        return "up", round(pct, 2)
    if pct < -TREND_FLAT_BAND_PCT:
        return "down", round(pct, 2)
    return "flat", round(pct, 2)


def price_board(db: Session, location: str | None = None) -> list[dict]:
    from app.core.constants import CATEGORY_CODES

    board: list[dict] = []
    for category in CATEGORY_CODES:
        best, _rid, _src = best_recycler_price(db, category, location)
        bench = benchmark_price(db, category, location)
        sources = (
            db.execute(
                select(func.count(MaterialPrice.price_id)).where(
                    MaterialPrice.material_category == category,
                    MaterialPrice.is_benchmark.is_(False),
                )
            ).scalar()
            or 0
        )
        price = best if best is not None else (Decimal(bench.buying_price) if bench else Decimal("0"))
        if best is not None and bench is not None:
            price = max(best, Decimal(bench.buying_price))
        trend, pct = _trend(db, category, location)
        board.append(
            {
                "material_category": category,
                "best_price": price,
                "benchmark_price": Decimal(bench.buying_price) if bench else None,
                "unit": "INR/kg",
                "currency": "INR",
                "trend": trend,
                "trend_pct": pct,
                "sources": int(sources),
                "is_estimate": True,
            }
        )
    return board
