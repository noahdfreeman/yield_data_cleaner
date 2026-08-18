# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic cleaning filter execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..filters.delays import apply_sensor_delays
from ..filters.local_outlier import evaluate_local_outlier_filter
from ..filters.motion import evaluate_motion_filters
from ..filters.overlap import evaluate_overlap_filter
from ..filters.pass_edge import evaluate_pass_edge_filters
from ..filters.quality import evaluate_quality_filters
from ..filters.ranges import evaluate_range_filters
from ..filters.swath import evaluate_swath_filters
from .recipe import CleaningRecipe


@dataclass
class CleaningRunResult:
    """Aggregated results and summary statistics of a cleaning run."""

    total_observations: int
    accepted_count: int
    excluded_count: int
    reason_counts: dict[str, int] = field(default_factory=dict)
    observation_updates: list[dict[str, Any]] = field(default_factory=list)
    recipe: CleaningRecipe = field(default_factory=CleaningRecipe)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_observations": self.total_observations,
            "accepted_count": self.accepted_count,
            "excluded_count": self.excluded_count,
            "accepted_percentage": (
                round((self.accepted_count / self.total_observations * 100.0), 2)
                if self.total_observations
                else 0.0
            ),
            "excluded_percentage": (
                round((self.excluded_count / self.total_observations * 100.0), 2)
                if self.total_observations
                else 0.0
            ),
            "reason_counts": dict(self.reason_counts),
            "recipe": self.recipe.to_dict(),
        }


def run_cleaning_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe | None = None,
) -> CleaningRunResult:
    """Execute the full sequence of deterministic cleaning filters against observations.

    Filters are evaluated non-destructively. Every exclusion reason is preserved
    and recorded in `filter_reasons`. Observations with 0 exclusion reasons are
    marked `accepted`; otherwise `excluded`.
    """
    if recipe is None:
        recipe = CleaningRecipe()

    n = len(observations)
    if n == 0:
        return CleaningRunResult(
            total_observations=0,
            accepted_count=0,
            excluded_count=0,
            recipe=recipe,
        )

    # 0. Optional sensor delay alignment
    working_obs = observations
    if recipe.apply_flow_delay or recipe.apply_moisture_delay:
        f_delay = recipe.flow_delay_s if recipe.apply_flow_delay else 0.0
        m_delay = recipe.moisture_delay_s if recipe.apply_moisture_delay else 0.0
        working_obs = apply_sensor_delays(
            observations, flow_delay_s=f_delay, moisture_delay_s=m_delay
        )

    # 1. Quality Filters
    quality_reasons = evaluate_quality_filters(working_obs, recipe)

    # 2. Motion Filters
    motion_reasons = evaluate_motion_filters(working_obs, recipe)

    # 3. Pass-Edge Filters
    pass_edge_reasons = evaluate_pass_edge_filters(working_obs, recipe)

    # 4. Swath Width Filters
    swath_reasons = evaluate_swath_filters(working_obs, recipe)

    # 5. Overlap Filters
    overlap_reasons = evaluate_overlap_filter(working_obs, recipe)

    # 6. Crop Yield & Moisture Range Filters
    range_reasons = evaluate_range_filters(working_obs, recipe)

    # 7. Local Spatial Outlier Filters
    outlier_reasons = evaluate_local_outlier_filter(working_obs, recipe)

    # Combine reason codes per observation
    obs_updates: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    accepted_count = 0
    excluded_count = 0

    for i in range(n):
        obs = working_obs[i]
        combined_reasons: list[str] = []

        # Preserve existing boundary exclusion if present
        existing_status = str(obs.get("boundary_status") or "")
        if existing_status == "outside_boundary":
            combined_reasons.append("outside_boundary")

        # Collect reasons from all stages
        for r_list in (
            quality_reasons[i],
            motion_reasons[i],
            pass_edge_reasons[i],
            swath_reasons[i],
            overlap_reasons[i],
            range_reasons[i],
            outlier_reasons[i],
        ):
            for code in r_list:
                if code not in combined_reasons:
                    combined_reasons.append(code)

        # Check existing manual action override if present
        manual_act = str(obs.get("manual_action") or "none")
        if manual_act == "exclude" and "manual_exclude" not in combined_reasons:
            combined_reasons.append("manual_exclude")
        elif manual_act == "restore":
            if "manual_restore" not in combined_reasons:
                combined_reasons.append("manual_restore")

        # Determine clean status
        if manual_act == "restore":
            clean_status = "accepted"
        elif combined_reasons:
            clean_status = "excluded"
        else:
            clean_status = "accepted"

        if clean_status == "accepted":
            accepted_count += 1
        else:
            excluded_count += 1

        for code in combined_reasons:
            reason_counts[code] = reason_counts.get(code, 0) + 1

        obs_updates.append(
            {
                "clean_status": clean_status,
                "filter_reasons": ";".join(combined_reasons),
                "filter_flags": str(len(combined_reasons)),
            }
        )

    return CleaningRunResult(
        total_observations=n,
        accepted_count=accepted_count,
        excluded_count=excluded_count,
        reason_counts=reason_counts,
        observation_updates=obs_updates,
        recipe=recipe,
    )
