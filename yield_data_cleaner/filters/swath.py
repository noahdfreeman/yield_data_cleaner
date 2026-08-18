# SPDX-License-Identifier: GPL-3.0-or-later
"""Swath width filters."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.recipe import CleaningRecipe


def evaluate_swath_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Evaluate minimum swath width and abrupt width transitions.

    Returns a list of reason code lists matching observation indices.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0:
        return results

    swaths: list[float | None] = []
    for obs in observations:
        w_val = obs.get("swath_width_m")
        if w_val is not None:
            try:
                w = float(w_val)
                swaths.append(w if math.isfinite(w) else None)
                continue
            except (TypeError, ValueError):
                pass
        swaths.append(None)

    for i in range(n):
        w = swaths[i]
        if w is not None and recipe.filter_min_swath and w < recipe.min_swath_width_m:
            results[i].append("swath_below_min")

    if recipe.filter_swath_change:
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
                w_curr = swaths[curr_idx]
                w_prev = swaths[prev_idx]
                if w_curr is not None and w_prev is not None:
                    if abs(w_curr - w_prev) > recipe.max_swath_change_m:
                        results[curr_idx].append("swath_change")

    return results
