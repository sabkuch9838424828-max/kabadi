"""Remove all artifacts created by scripts/e2e_test.py.

The E2E suite registers throwaway collectors/recyclers (emails matching
`e2e_%@test.in`) and creates lots/handovers/transactions against them. Those
records must never leak into a demo database, so the suite calls this at the
end and it can also be run standalone:

    python -m scripts.purge_e2e
"""
from __future__ import annotations

from sqlalchemy import delete, or_, select

from app.core.db import SessionLocal
from app.models.models import (
    AuditLog,
    Collector,
    FraudFlag,
    Handover,
    Lot,
    MaterialPrice,
    Recycler,
    Transaction,
    User,
)

E2E_EMAIL = "e2e_%@test.in"
E2E_RECYCLER_NAME = "E2E Green Recyclers%"


def purge() -> dict:
    db = SessionLocal()
    try:
        users = db.execute(select(User).where(User.email.like(E2E_EMAIL))).scalars().all()
        user_ids = [u.user_id for u in users]

        collectors = (
            db.execute(select(Collector).where(Collector.user_id.in_(user_ids)))
            .scalars()
            .all()
            if user_ids
            else []
        )
        collector_ids = [c.collector_id for c in collectors]

        recyclers = (
            db.execute(select(Recycler).where(Recycler.name.like(E2E_RECYCLER_NAME)))
            .scalars()
            .all()
        )
        recycler_ids = [r.recycler_id for r in recyclers]

        lot_filter = []
        if collector_ids:
            lot_filter.append(Lot.collector_id.in_(collector_ids))
        if recycler_ids:
            lot_filter.append(Lot.recycler_id.in_(recycler_ids))
        lots = db.execute(select(Lot).where(or_(*lot_filter))).scalars().all() if lot_filter else []
        lot_ids = [lot.lot_id for lot in lots]

        if lot_ids:
            db.execute(delete(Handover).where(Handover.lot_id.in_(lot_ids)))
            db.execute(delete(Transaction).where(Transaction.lot_id.in_(lot_ids)))
            db.execute(delete(FraudFlag).where(FraudFlag.lot_id.in_(lot_ids)))
            db.execute(delete(Lot).where(Lot.lot_id.in_(lot_ids)))
        if collector_ids:
            db.execute(delete(Transaction).where(Transaction.collector_id.in_(collector_ids)))
        if recycler_ids:
            db.execute(delete(MaterialPrice).where(MaterialPrice.recycler_id.in_(recycler_ids)))
            db.execute(delete(Recycler).where(Recycler.recycler_id.in_(recycler_ids)))
        if user_ids:
            db.execute(delete(Collector).where(Collector.user_id.in_(user_ids)))
            db.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(user_ids)))
            db.execute(delete(User).where(User.user_id.in_(user_ids)))
        db.commit()
        return {
            "users": len(user_ids),
            "recyclers": len(recycler_ids),
            "collectors": len(collector_ids),
            "lots": len(lot_ids),
        }
    finally:
        db.close()


if __name__ == "__main__":
    print("Purged:", purge())
