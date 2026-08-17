# SPDX-License-Identifier: GPL-3.0-or-later
"""Automated threshold recommendation engine using statistical distributions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .recipe import CleaningRecipe, default_recipe_for_crop


@dataclass
class RecommendationItem:
    """A single filter threshold recommendation with evidence and impact metrics."""

    parameter_name: str
    recommended_value: float
    current_value: float
    unit: str
    evidence: str
    affected_count: int
    affected_percentage: float
    confidence: float = 1.0


@dataclass
class RecommendationReport:
    """Full suite of automated recommendations for a dataset."""

    crop_code: str
    total_observations: int
    recommendations: dict[str, RecommendationItem] = field(default_factory=dict)
    recommended_recipe: CleaningRecipe = field(default_factory=CleaningRecipe)

    def to_dict(self) -> dict[str, Any]:
        return {
            "crop_code": self.crop_code,
            "total_observations": self.total_observations,
            "recommendations": {
                name: {
                    "parameter_name": item.parameter_name,
                    "recommended_value": round(item.recommended_value, 2),
                    "current_value": round(item.current_value, 2),
                    "unit": item.unit,
                    "evidence": item.evidence,
                    "affected_count": item.affected_count,
                    "affected_percentage": round(item.affected_percentage, 2),
                    "confidence": round(item.confidence, 2),
                }
                for name, item in self.recommendations.items()
            },
            "recommended_recipe": self.recommended_recipe.to_dict(),
        }


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    """Compute linear interpolated percentile on sorted float list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return d0 + d1


def generate_recommendations(
    observations: Sequence[Mapping[str, Any]],
    crop_code: str = "corn",
    unit_profile: str = "imperial",
) -> RecommendationReport:
    """Analyze observation distributions and generate recommended cleaning recipe thresholds."""
    recipe = default_recipe_for_crop(crop_code, unit_profile)
    n = len(observations)
    if n == 0:
        return RecommendationReport(
            crop_code=crop_code,
            total_observations=0,
            recommended_recipe=recipe,
        )

    # Extract valid numeric series
    yields: list[float] = []
    speeds: list[float] = []
    moistures: list[float] = []
    swaths: list[float] = []

    for obs in observations:
        y = obs.get("yield_wet_mass_area")
        if y is not None:
            try:
                val = float(y)
                if math.isfinite(val) and val > 0:
                    yields.append(val)
            except (TypeError, ValueError):
                pass

        s = obs.get("speed_m_s")
        if s is not None:
            try:
                val = float(s)
                if math.isfinite(val) and val > 0:
                    speeds.append(val)
            except (TypeError, ValueError):
                pass

        m = obs.get("moisture_pct")
        if m is not None:
            try:
                val = float(m)
                if math.isfinite(val) and val > 0:
                    moistures.append(val)
            except (TypeError, ValueError):
                pass

        w = obs.get("swath_width_m")
        if w is not None:
            try:
                val = float(w)
                if math.isfinite(val) and val > 0:
                    swaths.append(val)
            except (TypeError, ValueError):
                pass

    yields.sort()
    speeds.sort()
    moistures.sort()
    swaths.sort()

    recs: dict[str, RecommendationItem] = {}

    # 1. Yield bounds recommendation
    if yields:
        y_median = _percentile(yields, 50)
        y_q1 = _percentile(yields, 25)
        y_q3 = _percentile(yields, 75)
        y_iqr = max(1.0, y_q3 - y_q1)

        # Min yield: ~25% of median or Q1 - 1.5*IQR bounded by 10% median
        rec_min_y = max(y_median * 0.15, y_q1 - 1.5 * y_iqr)
        rec_min_y = max(rec_min_y, recipe.min_yield_kg_ha * 0.5)

        # Max yield: Q3 + 2.0*IQR
        rec_max_y = min(y_q3 + 2.5 * y_iqr, recipe.max_yield_kg_ha)

        aff_min_y = sum(1 for y in yields if y < rec_min_y)
        aff_max_y = sum(1 for y in yields if y > rec_max_y)

        recs["min_yield_kg_ha"] = RecommendationItem(
            parameter_name="min_yield_kg_ha",
            recommended_value=rec_min_y,
            current_value=recipe.min_yield_kg_ha,
            unit="kg/ha",
            evidence=f"Distribution Q1={round(y_q1, 1)}, Median={round(y_median, 1)}, IQR={round(y_iqr, 1)}",
            affected_count=aff_min_y,
            affected_percentage=(aff_min_y / n) * 100.0,
        )
        recs["max_yield_kg_ha"] = RecommendationItem(
            parameter_name="max_yield_kg_ha",
            recommended_value=rec_max_y,
            current_value=recipe.max_yield_kg_ha,
            unit="kg/ha",
            evidence=f"Distribution Q3={round(y_q3, 1)}, Upper fence Q3+2.5*IQR={round(y_q3 + 2.5 * y_iqr, 1)}",
            affected_count=aff_max_y,
            affected_percentage=(aff_max_y / n) * 100.0,
        )
        recipe.min_yield_kg_ha = rec_min_y
        recipe.max_yield_kg_ha = rec_max_y

    # 2. Speed bounds recommendation
    if speeds:
        s_median = _percentile(speeds, 50)
        s_p01 = _percentile(speeds, 1)
        s_p99 = _percentile(speeds, 99)

        rec_min_s = max(0.3, min(s_p01, 0.6))
        rec_max_s = max(s_p99, 4.0)

        aff_min_s = sum(1 for s in speeds if s < rec_min_s)
        aff_max_s = sum(1 for s in speeds if s > rec_max_s)

        recs["min_speed_m_s"] = RecommendationItem(
            parameter_name="min_speed_m_s",
            recommended_value=rec_min_s,
            current_value=recipe.min_speed_m_s,
            unit="m/s",
            evidence=f"1st percentile={round(s_p01, 2)} m/s, Median={round(s_median, 2)} m/s",
            affected_count=aff_min_s,
            affected_percentage=(aff_min_s / n) * 100.0,
        )
        recs["max_speed_m_s"] = RecommendationItem(
            parameter_name="max_speed_m_s",
            recommended_value=rec_max_s,
            current_value=recipe.max_speed_m_s,
            unit="m/s",
            evidence=f"99th percentile={round(s_p99, 2)} m/s, Median={round(s_median, 2)} m/s",
            affected_count=aff_max_s,
            affected_percentage=(aff_max_s / n) * 100.0,
        )
        recipe.min_speed_m_s = rec_min_s
        recipe.max_speed_m_s = rec_max_s

    # 3. Moisture bounds recommendation
    if moistures:
        m_q1 = _percentile(moistures, 25)
        m_q3 = _percentile(moistures, 75)
        m_median = _percentile(moistures, 50)
        m_iqr = max(0.5, m_q3 - m_q1)

        rec_min_m = max(recipe.min_moisture_pct, m_q1 - 2.0 * m_iqr)
        rec_max_m = min(recipe.max_moisture_pct, m_q3 + 2.0 * m_iqr)

        aff_min_m = sum(1 for m in moistures if m < rec_min_m)
        aff_max_m = sum(1 for m in moistures if m > rec_max_m)

        recs["min_moisture_pct"] = RecommendationItem(
            parameter_name="min_moisture_pct",
            recommended_value=rec_min_m,
            current_value=recipe.min_moisture_pct,
            unit="%",
            evidence=f"Median moisture={round(m_median, 1)}%, Q1-2*IQR={round(m_q1 - 2.0 * m_iqr, 1)}%",
            affected_count=aff_min_m,
            affected_percentage=(aff_min_m / n) * 100.0,
        )
        recs["max_moisture_pct"] = RecommendationItem(
            parameter_name="max_moisture_pct",
            recommended_value=rec_max_m,
            current_value=recipe.max_moisture_pct,
            unit="%",
            evidence=f"Median moisture={round(m_median, 1)}%, Q3+2*IQR={round(m_q3 + 2.0 * m_iqr, 1)}%",
            affected_count=aff_max_m,
            affected_percentage=(aff_max_m / n) * 100.0,
        )
        recipe.min_moisture_pct = rec_min_m
        recipe.max_moisture_pct = rec_max_m

    # 4. Swath width recommendation
    if swaths:
        w_median = _percentile(swaths, 50)
        rec_min_w = max(1.0, w_median * 0.25)
        aff_w = sum(1 for w in swaths if w < rec_min_w)

        recs["min_swath_width_m"] = RecommendationItem(
            parameter_name="min_swath_width_m",
            recommended_value=rec_min_w,
            current_value=recipe.min_swath_width_m,
            unit="m",
            evidence=f"Median full swath={round(w_median, 2)}m, 25% partial swath cutoff={round(rec_min_w, 2)}m",
            affected_count=aff_w,
            affected_percentage=(aff_w / n) * 100.0,
        )
        recipe.min_swath_width_m = rec_min_w

    return RecommendationReport(
        crop_code=crop_code,
        total_observations=n,
        recommendations=recs,
        recommended_recipe=recipe,
    )
