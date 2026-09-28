"""Anomaly detection for quoted prices and lots.

Uses an unsupervised statistical model (robust z-score via median/MAD, plus an
IsolationForest when enough history exists) over the historical price series so
that off-market quotes are flagged for fraud review — as required by the
documentation's AI/ML layer (section 5.D.3).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float
    severity: str
    method: str
    expected_range: tuple[float, float] | None
    detail: str


def _severity(z: float) -> str:
    if z >= 6:
        return "high"
    if z >= 4:
        return "medium"
    return "low"


def detect_price_anomaly(quoted: float, history: list[float]) -> AnomalyResult:
    """Robust z-score (median + MAD) — works with small hackathon-scale data."""
    series = np.asarray([h for h in history if h is not None and h > 0], dtype=float)
    if series.size < 4:
        return AnomalyResult(
            is_anomaly=False,
            score=0.0,
            severity="low",
            method="insufficient_history",
            expected_range=None,
            detail="Not enough price history yet to judge this quote.",
        )

    median = float(np.median(series))
    mad = float(np.median(np.abs(series - median)))
    # 1.4826 scales MAD to a standard-deviation equivalent for normal data.
    sigma = 1.4826 * mad
    if sigma <= 0:
        sigma = float(np.std(series)) or 1.0

    z = abs(quoted - median) / sigma
    low, high = median - 3 * sigma, median + 3 * sigma
    is_anom = z >= 3.5
    direction = "above" if quoted > median else "below"
    return AnomalyResult(
        is_anomaly=is_anom,
        score=round(float(z), 2),
        severity=_severity(z) if is_anom else "low",
        method="robust_zscore_median_mad",
        expected_range=(round(low, 2), round(high, 2)),
        detail=(
            f"Quoted price is {z:.1f} robust-sigma {direction} the historical median "
            f"of INR {median:.2f} for this category/location."
        ),
    )


def detect_outliers_isolation_forest(series: list[float], quoted: float) -> AnomalyResult | None:
    """Secondary model, only when there is enough data to fit it meaningfully."""
    data = np.asarray([h for h in series if h is not None and h > 0], dtype=float)
    if data.size < 20:
        return None
    try:
        from sklearn.ensemble import IsolationForest

        model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        model.fit(data.reshape(-1, 1))
        pred = model.predict(np.asarray([[quoted]]))
        score = float(model.score_samples(np.asarray([[quoted]]))[0])
        is_anom = bool(pred[0] == -1)
        return AnomalyResult(
            is_anomaly=is_anom,
            score=round(score, 4),
            severity="medium" if is_anom else "low",
            method="isolation_forest",
            expected_range=(round(float(data.min()), 2), round(float(data.max()), 2)),
            detail="IsolationForest outlier score on the category price series.",
        )
    except Exception:  # pragma: no cover - defensive
        return None


def detect_weight_anomaly(declared: float, verified: float) -> AnomalyResult:
    """Flag handovers where verified weight deviates sharply from declared."""
    if declared <= 0:
        return AnomalyResult(False, 0.0, "low", "declared_vs_verified", None, "Invalid declared weight")
    deviation = abs(verified - declared) / declared
    is_anom = deviation >= 0.20
    return AnomalyResult(
        is_anomaly=is_anom,
        score=round(deviation * 100, 2),
        severity="high" if deviation >= 0.40 else ("medium" if is_anom else "low"),
        method="declared_vs_verified_deviation",
        expected_range=(round(declared * 0.8, 3), round(declared * 1.2, 3)),
        detail=(
            f"Verified weight differs from declared by {deviation * 100:.1f}%. "
            "Trust-layer flag for manual review."
        ),
    )
