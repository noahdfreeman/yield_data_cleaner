# SPDX-License-Identifier: GPL-3.0-or-later
"""Crop-aware yield and moisture range filters."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.recipe import CleaningRecipe


def evaluate_range_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Evaluate crop-aware yield and moisture bounds.

    Returns a list of reason code lists matching observation indices.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0:
        return results

    for i, obs in enumerate(observations):
        # Yield checks (check dry yield then wet yield aliases)
        yield_val = None
        for k in ("yield_dry_mass_area", "yield_wet_mass_area", "dry_yield_mass_area", "yield", "dry_yield"):
            val = obs.get(k)
            if val is not None:
                yield_val = val
                break

        if yield_val is not None:
            try:
                y = float(yield_val)
                if math.isfinite(y):
                    if recipe.filter_min_yield and y < recipe.min_yield_kg_ha:
                        results[i].append("yield_below_min")
                    if recipe.filter_max_yield and y > recipe.max_yield_kg_ha:
                        results[i].append("yield_above_max")
            except (TypeError, ValueError):
                pass

        # Moisture checks
        m_val = obs.get("moisture_pct")
        if m_val is not None:
            try:
                m = float(m_val)
                if math.isfinite(m):
                    if recipe.filter_min_moisture and m < recipe.min_moisture_pct:
                        results[i].append("moisture_below_min")
                    if recipe.filter_max_moisture and m > recipe.max_moisture_pct:
                        results[i].append("moisture_above_max")
            except (TypeError, ValueError):
                pass

    return results
