"""SQLAlchemy ORM models for Kabadiwala Connect.

Table set and columns follow the PostgreSQL schema in the SIH26229 documentation
(section 6), extended with the fields required by the documented feature set
(user credentials for JWT auth, decline reasons, capacity, PII-minimisation, etc.).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )


class User(Base):
    """Auth principal. Role is one of collector / recycler / admin."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # collector/recycler/admin
    phone: Mapped[str | None] = mapped_column(String(15))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Collector(Base):
    __tablename__ = "collectors"

    collector_id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    display_name: Mapped[str | None] = mapped_column(String(150))
    preferred_language: Mapped[str] = mapped_column(String(10), default="hi", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(15))
    operating_location: Mapped[str | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User | None] = relationship()
    lots: Mapped[list[Lot]] = relationship(back_populates="collector")


class Recycler(Base):
    __tablename__ = "recyclers"

    recycler_id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), unique=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    facility_location: Mapped[str | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    materials_accepted: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # authorized / pending / unverified / suspended
    authorization_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    cpcb_registration_number: Mapped[str | None] = mapped_column(String(100))
    contact_details: Mapped[str | None] = mapped_column(String(100))
    service_area_radius_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), default=25)
    capacity_kg_per_day: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=1000)
    pickup_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User | None] = relationship()


class MaterialPrice(Base):
    __tablename__ = "material_prices"

    price_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sub_category: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(100), default="IN", nullable=False)
    buying_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="INR/kg", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="recycler", nullable=False)
    # recycler / msp_benchmark
    is_benchmark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recycler_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recyclers.recycler_id", ondelete="CASCADE")
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lot(Base):
    __tablename__ = "lots"

    lot_id: Mapped[uuid.UUID] = _pk()
    client_uuid: Mapped[str | None] = mapped_column(String(64), unique=True)
    collector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collectors.collector_id", ondelete="CASCADE"), nullable=False
    )
    material_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_sub_category: Mapped[str | None] = mapped_column(String(50))
    image_ref: Mapped[str | None] = mapped_column(Text)
    declared_weight: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    verified_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    recovery_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # JSON of estimated critical-mineral content (kg) + CO2 offset
    mineral_estimate: Mapped[dict | None] = mapped_column(JSONB)
    composition_basis: Mapped[dict | None] = mapped_column(JSONB)
    quoted_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    final_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    recycler_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recyclers.recycler_id", ondelete="SET NULL")
    )
    collection_location: Mapped[str | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    collection_district: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    # created / matched / handover / verified / declined / paid
    capture_mode: Mapped[str] = mapped_column(String(20), default="online")  # online / offline
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    collector: Mapped[Collector] = relationship(back_populates="lots")
    recycler: Mapped[Recycler | None] = relationship()
    handover: Mapped[Handover | None] = relationship(back_populates="lot", uselist=False)
    transaction: Mapped[Transaction | None] = relationship(back_populates="lot", uselist=False)


class Handover(Base):
    __tablename__ = "handovers"

    handover_id: Mapped[uuid.UUID] = _pk()
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lots.lot_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    photo_ref: Mapped[str | None] = mapped_column(Text)
    gps_location: Mapped[str | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    recycler_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    lot: Mapped[Lot] = relationship(back_populates="handover")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[uuid.UUID] = _pk()
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lots.lot_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    collector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collectors.collector_id", ondelete="CASCADE"), nullable=False
    )
    recycler_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recyclers.recycler_id", ondelete="SET NULL")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(10), default="cash", nullable=False)  # cash/upi
    payment_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/paid
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lot: Mapped[Lot] = relationship(back_populates="transaction")


class MaterialComposition(Base):
    """Stoichiometric composition ratios per material category.

    Values are *estimates* from published JNARDDC / industry ranges. They are
    ratios applied to a batch weight, NOT laboratory assay results.
    """

    __tablename__ = "material_compositions"
    __table_args__ = (UniqueConstraint("material_category", "element", name="uq_comp_cat_elem"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    element: Mapped[str] = mapped_column(String(20), nullable=False)  # Cu, Li, Co, Nd, Au, Ag...
    ratio_low: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)   # fraction of mass
    ratio_high: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    ratio_mid: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    # kg CO2e avoided per kg of this category recycled (vs virgin/landfill baseline)
    co2_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    source: Mapped[str] = mapped_column(String(150), default="JNARDDC/industry estimate")
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PriceHistory(Base):
    """Historical price snapshots used by the anomaly detector & trend arrows."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(100), default="IN", nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lots.lot_id", ondelete="CASCADE")
    )
    price_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("material_prices.price_id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(40), default="price_anomaly")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
