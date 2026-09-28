"""AI/ML endpoints: material classification and valuation."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.ml.classifier import MaterialClassifier
from app.schemas import schemas
from app.services import valuation

router = APIRouter(prefix="/ml", tags=["ai-ml"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024


@router.get("/model-info")
def model_info():
    clf = MaterialClassifier.instance()
    return {
        "model": clf.model_name,
        "available": clf.available,
        "load_error": clf.load_error,
        "method": "transfer learning (MobileNetV3-Small) + stoichiometric valuation",
        "valuation_method": "rule-based published stoichiometric composition ratios",
        "is_estimate": True,
        "disclaimer": (
            "Critical-mineral content is an estimate derived from published composition "
            "ratios applied to batch weight — not a laboratory assay."
        ),
    }


@router.get("/valuation-config")
def valuation_config(db: Session = Depends(get_db)):
    """Everything the offline PWA needs to compute the same valuation locally.

    Mirrors the server-side stoichiometric engine so an offline lot still gets a
    real estimated value + Recovery Score (reconciled against the server on sync).
    """
    from sqlalchemy import select

    from app.core.constants import CATEGORIES
    from app.ml.stoichiometry import (
        CRITICAL_ELEMENTS,
        ELEMENT_VALUE_INR_PER_KG,
        RECYCLABILITY,
        CO2_FULL_MARK_PER_KG,
        MINERAL_FULL_MARK_FRACTION,
        WEIGHT_CO2,
        WEIGHT_MINERALS,
        WEIGHT_RECYCLABILITY,
    )
    from app.models import MaterialComposition

    rows = db.execute(select(MaterialComposition)).scalars().all()
    compositions: dict[str, list[dict]] = {}
    for r in rows:
        compositions.setdefault(r.material_category, []).append(
            {
                "element": r.element,
                "ratio_low": str(r.ratio_low),
                "ratio_mid": str(r.ratio_mid),
                "ratio_high": str(r.ratio_high),
                "is_critical": r.is_critical,
                "co2_factor": str(r.co2_factor),
            }
        )
    return {
        "categories": CATEGORIES,
        "compositions": compositions,
        "element_values_inr_per_kg": {k: str(v) for k, v in ELEMENT_VALUE_INR_PER_KG.items()},
        "recyclability": {k: str(v) for k, v in RECYCLABILITY.items()},
        "critical_elements": sorted(CRITICAL_ELEMENTS),
        "score_weights": {
            "minerals": str(WEIGHT_MINERALS),
            "co2": str(WEIGHT_CO2),
            "recyclability": str(WEIGHT_RECYCLABILITY),
            "mineral_full_mark_fraction": str(MINERAL_FULL_MARK_FRACTION),
            "co2_full_mark_per_kg": str(CO2_FULL_MARK_PER_KG),
        },
        "is_estimate": True,
        "disclaimer": (
            "Critical-mineral content is an estimate from published stoichiometric "
            "composition ratios applied to batch weight — not a laboratory assay."
        ),
    }


@router.post("/classify", response_model=schemas.ClassifyOut)
async def classify(file: UploadFile = File(...)):
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB)")
    try:
        result = MaterialClassifier.instance().classify(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}") from exc
    return schemas.ClassifyOut(**result)


@router.get("/valuation", response_model=schemas.ValuationOut)
def valuation_endpoint(
    category: str = Query(...),
    weight_kg: Decimal = Query(..., gt=0, lt=100000),
    location: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Composition-aware instant valuation + Recovery Score."""
    from app.core.constants import CATEGORY_CODES

    if category not in CATEGORY_CODES:
        raise HTTPException(status_code=422, detail=f"Unknown category, allowed: {CATEGORY_CODES}")
    result = valuation.evaluate_lot(db, category, weight_kg, location=location)
    return schemas.ValuationOut(**result)
