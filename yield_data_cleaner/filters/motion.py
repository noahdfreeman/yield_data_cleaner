# SPDX-License-Identifier: GPL-3.0-or-later
"""Motion and header state filters."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.recipe import CleaningRecipe


def evaluate_motion_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Evaluate header status, speed limits, and sudden acceleration/deceleration.

    Returns a list of reason code lists matching observation indices.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0:
        return results

    speeds: list[float | None] = []
    for obs in observations:
        s_val = obs.get("speed_m_s")
        if s_val is not None:
            try:
                s = float(s_val)
                speeds.append(s if math.isfinite(s) else None)
                continue
            except (TypeError, ValueError):
                pass
        speeds.append(None)

    for i, obs in enumerate(observations):
        # Header disengaged
        if recipe.filter_header_disengaged:
            if obs.get("header_engaged") is False:
                results[i].append("header_disengaged")

        # Min / Max speed
        s = speeds[i]
        if s is not None:
            if recipe.filter_min_speed and s < recipe.min_speed_m_s:
                results[i].append("speed_below_min")
            if recipe.filter_max_speed and s > recipe.max_speed_m_s:
                results[i].append("speed_above_max")

    # Speed change within pass
    if recipe.filter_speed_change:
        pass_groups: dict[str, list[int]] = {}
        for i, obs in enumerate(observations):
            pass_id = str(obs.get("pass_id") or "unassigned")
            if pass_id not in pass_groups:
                pass_groups[pass_id] = []
            pass_groups[pass_id].append(i)

        for pass_id, indices in pass_groups.items():
            if pass_id == "unassigned" or len(indices) < 2:  # nosec B105
                continue

            for k in range(1, len(indices)):
                curr_idx = indices[k]
                prev_idx = indices[k - 1]
                s_curr = speeds[curr_idx]
                s_prev = speeds[prev_idx]
                if s_curr is not None and s_prev is not None:
                    if abs(s_curr - s_prev) > recipe.max_speed_change_m_s:
                        results[curr_idx].append("speed_change")

    return results
