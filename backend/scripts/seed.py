"""Seed the Kabadiwala Connect database.

Creates the schema, then loads:
  * stoichiometric material compositions (JNARDDC/industry estimate ranges)
  * Ministry of Mines MSP benchmark price board
  * CPCB-authorized recyclers + recycler-offered rates
  * demo accounts for all three roles
  * 45 days of price history (trend + anomaly detector training data)
  * sample verified lots so the Ministry analytics have real aggregates

Run:  python -m scripts.seed
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.ml.stoichiometry import CRITICAL_ELEMENTS
from app.models import (
    AuditLog,
    Collector,
    Handover,
    Lot,
    MaterialComposition,
    MaterialPrice,
    PriceHistory,
    Recycler,
    Transaction,
    User,
)
from app.services import serializers

random.seed(26229)

# ---------------------------------------------------------------- compositions
# Ratios = fraction of batch mass. Ranges are cited published estimates.
COMPOSITIONS: dict[str, list[tuple[str, float, float, float, float, bool]]] = {
    # element, low, mid, high, co2_factor(kg CO2e avoided / kg), is_critical
    "PCB": [
        ("Cu", 0.16, 0.19, 0.22, 3.2, False),
        ("Au", 0.0002, 0.0004, 0.0006, 0.0, True),
        ("Ag", 0.0008, 0.0014, 0.0020, 0.0, True),
        ("Pd", 0.00005, 0.00012, 0.00020, 0.0, True),
        ("Ta", 0.00010, 0.00025, 0.00040, 0.0, True),
        ("Ni", 0.010, 0.020, 0.030, 0.0, False),
        ("Fe", 0.050, 0.075, 0.100, 0.0, False),
        ("Pb", 0.010, 0.020, 0.030, 0.0, False),
    ],
    "battery": [
        ("Li", 0.020, 0.030, 0.040, 5.5, True),
        ("Co", 0.100, 0.150, 0.200, 0.0, True),
        ("Ni", 0.100, 0.150, 0.200, 0.0, False),
        ("Cu", 0.050, 0.075, 0.100, 0.0, False),
        ("Al", 0.050, 0.075, 0.100, 0.0, False),
        ("Fe", 0.030, 0.050, 0.070, 0.0, False),
    ],
    "motor_magnet": [
        ("Nd", 0.020, 0.035, 0.050, 2.5, True),
        ("Fe", 0.400, 0.550, 0.700, 0.0, False),
        ("Cu", 0.050, 0.100, 0.150, 0.0, False),
        ("Al", 0.030, 0.055, 0.080, 0.0, False),
        ("Ni", 0.005, 0.012, 0.020, 0.0, False),
    ],
    "cable": [
        ("Cu", 0.400, 0.550, 0.700, 2.0, False),
        ("Al", 0.050, 0.120, 0.200, 0.0, False),
        ("Pb", 0.002, 0.005, 0.010, 0.0, False),
    ],
    "CRT": [
        ("Pb", 0.100, 0.180, 0.250, 1.2, False),
        ("Cu", 0.020, 0.035, 0.050, 0.0, False),
        ("Ba", 0.010, 0.020, 0.030, 0.0, False),
        ("Fe", 0.050, 0.080, 0.120, 0.0, False),
    ],
    "LCD": [
        ("In", 0.00010, 0.00030, 0.00050, 1.8, True),
        ("Cu", 0.010, 0.020, 0.030, 0.0, False),
        ("Au", 0.00002, 0.00005, 0.00009, 0.0, True),
        ("Al", 0.020, 0.035, 0.050, 0.0, False),
    ],
    "mixed_plastic": [
        ("Cu", 0.001, 0.005, 0.010, 1.0, False),
        ("Al", 0.005, 0.012, 0.020, 0.0, False),
    ],
    "other": [
        ("Cu", 0.050, 0.100, 0.150, 1.5, False),
        ("Fe", 0.200, 0.350, 0.500, 0.0, False),
        ("Al", 0.050, 0.100, 0.150, 0.0, False),
    ],
}

# MSP benchmark prices (INR/kg) — indicative Ministry of Mines style board.
MSP_BENCHMARKS: dict[str, float] = {
    "PCB": 220.0,
    "battery": 150.0,
    "motor_magnet": 90.0,
    "cable": 480.0,
    "CRT": 25.0,
    "LCD": 45.0,
    "mixed_plastic": 18.0,
    "other": 60.0,
}

# location -> district coords for seeding
LOCATIONS = {
    "Pune": (18.5204, 73.8567, "Maharashtra"),
    "Mumbai": (19.0760, 72.8777, "Maharashtra"),
    "Nagpur": (21.1458, 79.0882, "Maharashtra"),
    "Nashik": (19.9975, 73.7898, "Maharashtra"),
    "Thane": (19.2183, 72.9781, "Maharashtra"),
    "Aurangabad": (19.8762, 75.3433, "Maharashtra"),
}

RECYCLERS = [
    # name, district, materials, status, cpcb reg, radius, capacity, pickup, price multiplier
    ("GreenLoop E-Waste Pvt Ltd", "Pune", None, "authorized", "CPCB/EW/2019/MH-0412", 45, 2500, True, 1.08),
    ("EcoRecycle India — Chakan Hub", "Pune", ["PCB", "battery", "cable", "motor_magnet"], "authorized",
     "CPCB/EW/2020/MH-0781", 60, 6000, True, 1.12),
    ("Mumbai Metal Recovery LLP", "Mumbai", ["cable", "PCB", "motor_magnet", "other"], "authorized",
     "CPCB/EW/2018/MH-0199", 80, 9000, False, 1.05),
    ("Nagpur Urban Miners", "Nagpur", ["PCB", "CRT", "LCD", "mixed_plastic"], "pending",
     "CPCB/EW/2024/MH-3310", 50, 1500, False, 0.98),
    ("Nashik Green Metals", "Nashik", ["battery", "motor_magnet", "other", "cable"], "authorized",
     "CPCB/EW/2021/MH-1450", 40, 2200, True, 1.02),
    ("Thane Recyclers Co-op", "Thane", None, "unverified", None, 30, 900, False, 0.88),
]

COLLECTORS = [
    ("Ravi Kumar", "ravi@kabadiwala.in", "hi", "Pune"),
    ("Sunita Pawar", "sunita@kabadiwala.in", "mr", "Pune"),
    ("Iqbal Shaikh", "iqbal@kabadiwala.in", "hi", "Mumbai"),
    ("Dilip Yadav", "dilip@kabadiwala.in", "mr", "Nagpur"),
    ("Meena Devi", "meena@kabadiwala.in", "hi", "Nashik"),
    ("Arjun Patil", "arjun@kabadiwala.in", "mr", "Thane"),
]


def _repeat(ratio: tuple[float, float, float]) -> tuple[float, float, float]:
    return ratio


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def seed_compositions(db) -> None:
    if db.execute(select(MaterialComposition).limit(1)).scalars().first():
        return
    for category, rows in COMPOSITIONS.items():
        for element, low, mid, high, co2, critical in rows:
            db.add(
                MaterialComposition(
                    material_category=category,
                    element=element,
                    ratio_low=Decimal(str(low)),
                    ratio_mid=Decimal(str(mid)),
                    ratio_high=Decimal(str(high)),
                    co2_factor=Decimal(str(co2)),
                    is_critical=critical or element in CRITICAL_ELEMENTS,
                    source="JNARDDC/industry estimate ranges",
                )
            )
    db.commit()


def seed_users_and_profiles(db) -> dict:
    if db.execute(select(User).limit(1)).scalars().first():
        return {}

    created: dict = {"recyclers": [], "collectors": []}

    admin = User(
        email="admin@kabadiwala.gov.in",
        hashed_password=hash_password("Admin@12345"),
        full_name="Ministry Administrator",
        role="admin",
    )
    db.add(admin)

    for name, district, materials, status, cpcb, radius, capacity, pickup, mult in RECYCLERS:
        email = name.split()[0].lower().replace("—", "") + "@recycler.in"
        user = User(
            email=email,
            hashed_password=hash_password("Recycler@123"),
            full_name=name,
            role="recycler",
        )
        db.add(user)
        db.flush()
        lat, lon, state = LOCATIONS[district]
        recycler = Recycler(
            user_id=user.user_id,
            name=name,
            facility_location=WKTElement(f"POINT({lon} {lat})", srid=4326),
            district=district,
            state=state,
            materials_accepted=materials or [],
            authorization_status=status,
            registration_number=cpcb.replace("CPCB/EW/", "REG/") if cpcb else None,
            cpcb_registration_number=cpcb,
            contact_details=f"+91-98{random.randint(10000000, 99999999)}",
            service_area_radius_km=Decimal(str(radius)),
            capacity_kg_per_day=Decimal(str(capacity)),
            pickup_available=pickup,
        )
        db.add(recycler)
        db.flush()
        created["recyclers"].append((recycler, mult))

    for i, (name, email, lang, district) in enumerate(COLLECTORS):
        user = User(
            email=email,
            hashed_password=hash_password("Collector@123" if i else "Collector@123"),
            full_name=name,
            role="collector",
            phone=f"+9198{random.randint(10000000, 99999999)}",
        )
        db.add(user)
        db.flush()
        lat, lon, state = LOCATIONS[district]
        collector = Collector(
            user_id=user.user_id,
            display_name=name,
            preferred_language=lang,
            phone=user.phone,
            operating_location=WKTElement(f"POINT({lon} {lat})", srid=4326),
            district=district,
            state=state,
        )
        db.add(collector)
        db.flush()
        created["collectors"].append(collector)

    db.commit()
    return created


def seed_prices(db, recyclers: list[tuple]) -> None:
    if db.execute(select(MaterialPrice).limit(1)).scalars().first():
        return
    from app.core.constants import CATEGORY_CODES

    now = datetime.now(timezone.utc)

    # MSP benchmarks (national + per-district echo)
    for category, price in MSP_BENCHMARKS.items():
        db.add(
            MaterialPrice(
                material_category=category,
                location="IN",
                buying_price=Decimal(str(price)),
                unit="INR/kg",
                source="msp_benchmark",
                is_benchmark=True,
            )
        )
        for district in LOCATIONS:
            jitter = 1 + random.uniform(-0.03, 0.03)
            db.add(
                MaterialPrice(
                    material_category=category,
                    location=district,
                    buying_price=Decimal(str(round(price * jitter, 2))),
                    unit="INR/kg",
                    source="msp_benchmark",
                    is_benchmark=True,
                    recorded_at=now - timedelta(hours=random.randint(1, 72)),
                )
            )

    # recycler offers
    for recycler, mult in recyclers:
        categories = recycler.materials_accepted or CATEGORY_CODES
        for category in categories:
            base = MSP_BENCHMARKS[category] * mult
            price = round(base * (1 + random.uniform(-0.04, 0.06)), 2)
            db.add(
                MaterialPrice(
                    material_category=category,
                    location=recycler.district or "IN",
                    buying_price=Decimal(str(price)),
                    unit="INR/kg",
                    source="recycler",
                    is_benchmark=False,
                    recycler_id=recycler.recycler_id,
                    recorded_at=now - timedelta(hours=random.randint(1, 96)),
                )
            )

    db.commit()


def seed_price_history(db) -> None:
    if db.execute(select(PriceHistory).limit(1)).scalars().first():
        return
    now = datetime.now(timezone.utc)
    for category, base in MSP_BENCHMARKS.items():
        for day in range(45, 0, -1):
            drift = 1 + random.uniform(-0.05, 0.05)
            # gentle upward trend for the mineral-rich categories
            trend = 1 + (45 - day) * (0.0015 if category in {"PCB", "battery", "cable"} else 0.0002)
            price = round(base * drift * trend, 2)
            db.add(
                PriceHistory(
                    material_category=category,
                    location="IN",
                    price=Decimal(str(price)),
                    recorded_at=now - timedelta(days=day),
                )
            )
    db.commit()


def seed_sample_activity(db, collectors: list[Collector], recyclers: list[tuple]) -> None:
    if db.execute(select(Lot).limit(1)).scalars().first():
        return
    from app.core.constants import CATEGORY_CODES
    from app.services import valuation

    now = datetime.now(timezone.utc)
    authorized = [r for r, _ in recyclers if r.authorization_status == "authorized"]

    for i in range(40):
        collector = random.choice(collectors)
        recycler = random.choice(authorized)
        category = random.choice(CATEGORY_CODES)
        declared = Decimal(str(round(random.uniform(2, 60), 2)))
        verified = (declared * Decimal(str(round(random.uniform(0.9, 1.06), 3)))).quantize(
            Decimal("0.001")
        )

        result = valuation.evaluate_lot(db, category, declared, location=collector.district)
        unit_price = result["price_used"]
        final = (unit_price * verified).quantize(Decimal("0.01"))

        created_at = now - timedelta(days=random.randint(0, 44), hours=random.randint(0, 23))
        lat, lon, _ = LOCATIONS[collector.district or "Pune"]

        lot = Lot(
            collector_id=collector.collector_id,
            material_category=category,
            image_ref=None,
            declared_weight=declared,
            verified_weight=verified,
            estimated_value=result["estimated_value"],
            recovery_score=result["recovery_score"],
            quoted_price=unit_price,
            final_price=final,
            mineral_estimate=valuation.mineral_estimate_payload(result),
            composition_basis=result["composition_basis"],
            recycler_id=recycler.recycler_id,
            collection_location=WKTElement(
                f"POINT({lon + random.uniform(-0.3, 0.3)} {lat + random.uniform(-0.3, 0.3)})",
                srid=4326,
            ),
            collection_district=collector.district,
            status=random.choice(["verified", "paid", "paid", "verified"]),
            capture_mode=random.choice(["online", "online", "offline"]),
            created_at=created_at,
            updated_at=created_at + timedelta(hours=random.randint(1, 30)),
        )
        db.add(lot)
        db.flush()

        db.add(
            Handover(
                lot_id=lot.lot_id,
                photo_ref=f"local://handover/{lot.lot_id}.jpg",
                gps_location=lot.collection_location,
                captured_at=created_at + timedelta(hours=random.randint(1, 12)),
                reference_number=f"KC-{(collector.district or 'IND')[:3].upper()}-{random.randint(100000, 999999)}",
                recycler_confirmation=True,
                confirmed_at=created_at + timedelta(hours=random.randint(13, 20)),
            )
        )
        db.add(
            Transaction(
                lot_id=lot.lot_id,
                collector_id=collector.collector_id,
                recycler_id=recycler.recycler_id,
                amount=final,
                payment_mode=random.choice(["cash", "cash", "upi"]),
                payment_status="paid",
                paid_at=created_at + timedelta(hours=random.randint(13, 22)),
                created_at=created_at + timedelta(hours=random.randint(12, 20)),
            )
        )

    db.add(
        AuditLog(
            actor_role="admin",
            action="seed_database",
            entity="system",
            detail={"note": "Initial demo dataset seeded", "lots": 40},
        )
    )
    db.commit()


def main() -> int:
    print("→ creating schema")
    create_schema()
    db = SessionLocal()
    try:
        print("→ seeding stoichiometric compositions")
        seed_compositions(db)
        print("→ seeding users, recyclers, collectors")
        created = seed_users_and_profiles(db)
        if not created:
            print("   (data already present — skipping seed)")
            return 0
        print("→ seeding price board (MSP benchmarks + recycler rates)")
        seed_prices(db, created["recyclers"])
        print("→ seeding 45 days of price history")
        seed_price_history(db)
        print("→ seeding sample verified lots / handovers / transactions")
        seed_sample_activity(db, created["collectors"], created["recyclers"])
        print("\n✓ Seed complete.")
        print("\nDemo accounts (username = email, password):")
        print("  admin      admin@kabadiwala.gov.in        Admin@12345")
        print("  collector  ravi@kabadiwala.in             Collector@123")
        print("  recycler   greenloop@recycler.in          Recycler@123")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
