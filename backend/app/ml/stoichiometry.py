"""Stoichiometric valuation engine.

Turns (material category, weight) into:
  * estimated content of recoverable elements (kg)
  * an estimated cash value (INR) from the price board
  * a Recovery Score (0-100)
  * an estimated CO2 offset

IMPORTANT HONESTY NOTE (as required by the SIH26229 documentation, Jury Q&A):
the element ratios below are *published-range approximations* (JNARDDC /
industry stoichiometric composition ratios) applied to batch mass. They are
NOT laboratory assay measurements. Every API response that uses this engine
carries `is_estimate=True` and a disclaimer, and the ratio ranges are returned
to the client so the assumption is visible.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

D = Decimal


def _d(value) -> Decimal:
    return value if isinstance(value, Decimal) else D(str(value))


def _q(value: Decimal, places: str = "0.001") -> Decimal:
    return value.quantize(D(places), rounding=ROUND_HALF_UP)


# Recovery-score weights (transparent, documented).
WEIGHT_MINERALS = D("55")      # how much critical-mineral mass is recoverable
WEIGHT_CO2 = D("30")           # climate benefit per kg
WEIGHT_RECYCLABILITY = D("15") # material-handling merit

# Normalisation references used by the score.
MINERAL_FULL_MARK_FRACTION = D("0.25")  # 25% of batch mass being critical minerals => full marks
CO2_FULL_MARK_PER_KG = D("8.0")         # 8 kg CO2e avoided per kg => full marks

# Per-category recyclability factor (0-1): how well the formal chain recovers it.
RECYCLABILITY: dict[str, Decimal] = {
    "PCB": D("0.95"),
    "battery": D("0.90"),
    "motor_magnet": D("0.85"),
    "cable": D("0.95"),
    "CRT": D("0.55"),
    "LCD": D("0.65"),
    "mixed_plastic": D("0.50"),
    "other": D("0.45"),
}

# Critical minerals as defined in the problem statement (India imports 90-100%).
CRITICAL_ELEMENTS = {"Li", "Co", "Nd", "Ta", "Ga", "In", "Au", "Ag", "Pd", "Pt"}

# Indicative recovery value (INR/kg) for the *contained* element. Used only to
# show the collector where the hidden value sits; the cash price they are paid
# comes from the price board, not from this table.
ELEMENT_VALUE_INR_PER_KG: dict[str, Decimal] = {
    "Cu": D("780"),
    "Li": D("1800"),
    "Co": D("2600"),
    "Nd": D("5200"),
    "Ta": D("14000"),
    "Ga": D("15000"),
    "In": D("22000"),
    "Au": D("5200000"),
    "Ag": D("75000"),
    "Pd": D("2600000"),
    "Pt": D("2400000"),
    "Pb": D("180"),
    "Ni": D("1300"),
    "Al": D("190"),
    "Fe": D("35"),
}

DISCLAIMER = (
    "Estimated using published stoichiometric composition ratios for the material "
    "category. This is an approximation, not a laboratory assay. Actual recovery "
    "depends on the specific device, its age and the recycler's process."
)


def recovery_score(
    weight_kg: Decimal,
    minerals: dict[str, dict],
    co2_offset_kg: Decimal,
    category: str,
) -> Decimal:
    """0-100 score: how much hidden value + climate benefit this batch carries."""
    weight_kg = _d(weight_kg)
    if weight_kg <= 0:
        return D("0")

    critical_kg = sum(
        (_d(m["kg_mid"]) for el, m in minerals.items() if el in CRITICAL_ELEMENTS),
        D("0"),
    )
    mineral_fraction = critical_kg / weight_kg
    mineral_component = min(mineral_fraction / MINERAL_FULL_MARK_FRACTION, D("1")) * WEIGHT_MINERALS

    co2_per_kg = _d(co2_offset_kg) / weight_kg if weight_kg else D("0")
    co2_component = min(co2_per_kg / CO2_FULL_MARK_PER_KG, D("1")) * WEIGHT_CO2

    recyclability_component = RECYCLABILITY.get(category, D("0.45")) * WEIGHT_RECYCLABILITY

    score = mineral_component + co2_component + recyclability_component
    return _q(min(score, D("100")), "0.01")


def evaluate(
    category: str,
    weight_kg: Decimal,
    compositions: list[dict],
    price: Decimal,
    price_source: str,
    co2_factor: Decimal,
) -> dict:
    """Full valuation result.

    `compositions` is a list of rows with keys:
      element, ratio_low, ratio_high, ratio_mid, is_critical
    """
    weight_kg = _d(weight_kg)
    minerals: dict[str, dict] = {}
    for row in compositions:
        el = row["element"]
        low = _q(_d(row["ratio_low"]) * weight_kg)
        mid = _q(_d(row["ratio_mid"]) * weight_kg)
        high = _q(_d(row["ratio_high"]) * weight_kg)
        value = _q(mid * ELEMENT_VALUE_INR_PER_KG.get(el, D("0")), "0.01")
        minerals[el] = {
            "element": el,
            "kg_low": low,
            "kg_mid": mid,
            "kg_high": high,
            "is_critical": bool(row.get("is_critical", el in CRITICAL_ELEMENTS)),
            "value_inr": value,
            "ratio_low": str(row["ratio_low"]),
            "ratio_high": str(row["ratio_high"]),
        }

    estimated_value = _q(_d(price) * weight_kg, "0.01")
    co2_offset = _q(_d(co2_factor) * weight_kg, "0.001")
    score = recovery_score(weight_kg, minerals, co2_offset, category)

    return {
        "material_category": category,
        "declared_weight": _q(weight_kg),
        "estimated_value": estimated_value,
        "price_used": _q(_d(price), "0.01"),
        "price_source": price_source,
        "recovery_score": score,
        "co2_offset_kg": co2_offset,
        "minerals": minerals,
        "is_estimate": True,
        "disclaimer": DISCLAIMER,
    }
