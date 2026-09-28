"""Pydantic request/response schemas — the API contract."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["collector", "recycler", "admin"]


# ---------------------------------------------------------------- auth
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=150)
    role: Role = "collector"
    phone: str | None = Field(default=None, max_length=15)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        digits = "".join(c for c in v if c.isdigit() or c == "+")
        if len(digits) < 6:
            raise ValueError("phone looks invalid")
        return digits


class CollectorProfileIn(BaseModel):
    preferred_language: Literal["hi", "mr", "en"] = "hi"
    display_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=15)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)


class RecyclerProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    materials_accepted: list[str] = Field(default_factory=list)
    registration_number: str | None = Field(default=None, max_length=100)
    cpcb_registration_number: str | None = Field(default=None, max_length=100)
    contact_details: str | None = Field(default=None, max_length=100)
    service_area_radius_km: Decimal | None = Field(default=Decimal("25"), ge=0, le=2000)
    capacity_kg_per_day: Decimal | None = Field(default=Decimal("1000"), ge=0)
    pickup_available: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: uuid.UUID
    full_name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    phone: str | None = None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------- prices
class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price_id: int
    material_category: str
    sub_category: str | None = None
    location: str
    buying_price: Decimal
    unit: str
    source: str
    is_benchmark: bool
    recycler_id: uuid.UUID | None = None
    recorded_at: datetime


class PriceBoardEntry(BaseModel):
    material_category: str
    best_price: Decimal
    benchmark_price: Decimal | None = None
    unit: str
    currency: str = "INR"
    trend: Literal["up", "down", "flat"]
    trend_pct: float
    sources: int
    is_estimate: bool = True


class PriceCreate(BaseModel):
    material_category: str
    sub_category: str | None = None
    location: str = "IN"
    buying_price: Decimal = Field(gt=0, lt=Decimal("1000000"))
    unit: str = "INR/kg"
    is_benchmark: bool = False


class BenchmarkCreate(PriceCreate):
    is_benchmark: bool = True


# ---------------------------------------------------------------- valuation / ml
class ClassifyOut(BaseModel):
    material_category: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    model: str
    is_estimate: bool = True
    disclaimer: str


class MineralEstimate(BaseModel):
    element: str
    kg_low: Decimal
    kg_mid: Decimal
    kg_high: Decimal
    is_critical: bool = False
    value_inr: Decimal | None = None


class ValuationOut(BaseModel):
    material_category: str
    declared_weight: Decimal
    unit: str = "kg"
    estimated_value: Decimal
    price_used: Decimal
    price_source: str
    recovery_score: Decimal = Field(ge=0, le=100)
    co2_offset_kg: Decimal
    minerals: list[MineralEstimate]
    critical_minerals_basis: str | None = None
    anomaly: dict[str, Any] | None = None
    is_estimate: bool = True
    disclaimer: str

    @field_validator("minerals", mode="before")
    @classmethod
    def _minerals_to_list(cls, value):
        # The engine emits an element-keyed mapping; the API contract is a list.
        if isinstance(value, dict):
            return list(value.values())
        return value


# ---------------------------------------------------------------- recyclers
class RecyclerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recycler_id: uuid.UUID
    name: str
    district: str | None = None
    state: str | None = None
    materials_accepted: list[str] = Field(default_factory=list)
    authorization_status: str
    registration_number: str | None = None
    cpcb_registration_number: str | None = None
    contact_details: str | None = None
    service_area_radius_km: Decimal | None = None
    capacity_kg_per_day: Decimal | None = None
    pickup_available: bool
    latitude: float | None = None
    longitude: float | None = None


class RecyclerMatch(RecyclerOut):
    distance_km: float | None = None
    offered_price: Decimal | None = None
    rank_score: float
    rank_reasons: list[str] = Field(default_factory=list)


class AuthorizationUpdate(BaseModel):
    authorization_status: Literal["authorized", "pending", "unverified", "suspended"]
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------- lots
class LotCreate(BaseModel):
    client_uuid: str | None = Field(default=None, max_length=64)
    material_category: str
    material_sub_category: str | None = None
    declared_weight: Decimal = Field(gt=0, lt=Decimal("100000"))
    image_ref: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    district: str | None = None
    capture_mode: Literal["online", "offline"] = "online"
    created_at_client: datetime | None = None

    @field_validator("material_category")
    @classmethod
    def _cat(cls, v: str) -> str:
        from app.core.constants import CATEGORY_CODES

        if v not in CATEGORY_CODES:
            raise ValueError(f"unknown material_category; allowed: {CATEGORY_CODES}")
        return v


class LotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lot_id: uuid.UUID
    client_uuid: str | None = None
    collector_id: uuid.UUID
    material_category: str
    material_sub_category: str | None = None
    image_ref: str | None = None
    declared_weight: Decimal
    verified_weight: Decimal | None = None
    estimated_value: Decimal | None = None
    recovery_score: Decimal | None = None
    mineral_estimate: dict | None = None
    composition_basis: dict | None = None
    quoted_price: Decimal | None = None
    final_price: Decimal | None = None
    recycler_id: uuid.UUID | None = None
    recycler_name: str | None = None
    collection_district: str | None = None
    status: str
    capture_mode: str
    created_at: datetime
    updated_at: datetime


class LotMatchIn(BaseModel):
    recycler_id: uuid.UUID


# ---------------------------------------------------------------- handover
class HandoverCreate(BaseModel):
    photo_ref: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=500)
    captured_at: datetime | None = None
    client_uuid: str | None = None


class HandoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    handover_id: uuid.UUID
    lot_id: uuid.UUID
    photo_ref: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    captured_at: datetime
    reference_number: str
    recycler_confirmation: bool
    confirmed_at: datetime | None = None
    notes: str | None = None


class VerifyWeightIn(BaseModel):
    verified_weight: Decimal = Field(gt=0, lt=Decimal("100000"))
    payment_mode: Literal["cash", "upi"] = "cash"
    notes: str | None = Field(default=None, max_length=500)


class DeclineIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# ---------------------------------------------------------------- transactions
class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transaction_id: uuid.UUID
    lot_id: uuid.UUID
    collector_id: uuid.UUID
    recycler_id: uuid.UUID | None = None
    amount: Decimal
    payment_mode: str
    payment_status: str
    paid_at: datetime | None = None
    created_at: datetime


class LedgerOut(BaseModel):
    total_earned: Decimal
    pending_dues: Decimal
    lifetime_lots: int
    lifetime_kg: Decimal
    transactions: list[TransactionOut]


# ---------------------------------------------------------------- analytics
class AnalyticsOut(BaseModel):
    total_lots: int
    total_declared_kg: Decimal
    total_verified_kg: Decimal
    material_collected_kg: Decimal
    active_collectors: int
    active_recyclers: int
    authorized_recyclers: int
    critical_minerals_recovered: list[dict[str, Any]]
    co2_offset_kg: Decimal
    recovery_score_avg: Decimal | None = None
    district_heatmap: list[dict[str, Any]]
    category_breakdown: list[dict[str, Any]]
    declared_vs_verified: dict[str, Any]
    price_anomalies: int
    is_estimate_disclaimer: str


class TrendPoint(BaseModel):
    material_category: str
    points: list[dict[str, Any]]


# ---------------------------------------------------------------- profiles (defined last:
# they reference schemas declared above so the module imports cleanly)
class CollectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    collector_id: uuid.UUID
    display_name: str | None = None
    preferred_language: str
    phone: str | None = None
    district: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LotDetail(LotOut):
    handover: "HandoverOut | None" = None
    transaction: "TransactionOut | None" = None


class MeOut(BaseModel):
    user: UserOut
    collector: CollectorOut | None = None
    recycler: RecyclerOut | None = None


class LotSyncItem(LotCreate):
    """Offline-created lot plus the optional match/handover captured offline."""

    recycler_id: uuid.UUID | None = None
    handover: "HandoverCreate | None" = None
