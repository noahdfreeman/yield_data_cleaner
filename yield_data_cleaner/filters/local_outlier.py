# SPDX-License-Identifier: GPL-3.0-or-later
"""Robust local spatial outlier filter."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.pass_reconstruction import get_point_coordinate
from ..core.recipe import CleaningRecipe


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = len(sorted_v)
    mid = k // 2
    if k % 2 == 1:
        return sorted_v[mid]
    return (sorted_v[mid - 1] + sorted_v[mid]) / 2.0


def evaluate_local_outlier_filter(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Detect local spatial yield outliers using neighborhood median and MAD.

    Points that deviate significantly from their immediate spatial neighborhood are
    flagged as `local_yield_outlier`.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0 or not recipe.filter_local_outlier:
        return results

    radius = max(5.0, recipe.local_outlier_radius_m)
    coords = [get_point_coordinate(obs) for obs in observations]
    sample_pt = next((pt for pt in coords if pt is not None), None)
    is_geo = (
        sample_pt is not None
        and (10.0 < abs(sample_pt[0]) <= 180.0)
        and (10.0 < abs(sample_pt[1]) <= 90.0)
    )
    mean_lat_rad = math.radians(sample_pt[1]) if (is_geo and sample_pt) else 0.0
    cos_lat = math.cos(mean_lat_rad) if is_geo else 1.0

    projected_coords = []
    for pt in coords:
        if pt is None:
            projected_coords.append(None)
        elif is_geo:
            projected_coords.append((pt[0] * 111320.0 * cos_lat, pt[1] * 110540.0))
        else:
            projected_coords.append(pt)

    yields: list[float | None] = []

    for obs in observations:
        y_val = None
        for k in (
            "yield_dry_mass_area",
            "yield_wet_mass_area",
            "dry_yield_mass_area",
            "yield",
            "dry_yield",
        ):
            val = obs.get(k)
            if val is not None:
                y_val = val
                break
        if y_val is not None:
            try:
                y = float(y_val)
                yields.append(y if math.isfinite(y) and y > 0 else None)
                continue
            except (TypeError, ValueError):
                pass
        yields.append(None)

    # Build spatial grid index
    cell_size = radius
    grid: dict[tuple[int, int], list[int]] = {}

    for i in range(n):
        pt = projected_coords[i]
        if pt is None or yields[i] is None:
            continue
        gx = int(math.floor(pt[0] / cell_size))
        gy = int(math.floor(pt[1] / cell_size))
        grid.setdefault((gx, gy), []).append(i)

    # Evaluate each observation against its local neighborhood
    for i in range(n):
        pt = projected_coords[i]
        y = yields[i]
        if pt is None or y is None:
            continue

        gx = int(math.floor(pt[0] / cell_size))
        gy = int(math.floor(pt[1] / cell_size))

        # Collect neighbors within radius
        neighbor_yields: list[float] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell_key = (gx + dx, gy + dy)
                if cell_key in grid:
                    for idx in grid[cell_key]:
                        other_pt = projected_coords[idx]
                        other_y = yields[idx]
                        if other_pt is not None and other_y is not None:
                            if math.hypot(pt[0] - other_pt[0], pt[1] - other_pt[1]) <= radius:
                                neighbor_yields.append(other_y)

        if len(neighbor_yields) < recipe.local_outlier_min_neighbors:
            continue

        med = _median(neighbor_yields)
        deviations = [abs(val - med) for val in neighbor_yields]
        mad = _median(deviations)
        robust_std = 1.4826 * mad

        # If MAD is near zero, fallback to sample standard deviation
        if robust_std < 1e-6:
            mean = sum(neighbor_yields) / len(neighbor_yields)
            var = sum((v - mean) ** 2 for v in neighbor_yields) / len(neighbor_yields)
            robust_std = math.sqrt(var)

        if robust_std > 1e-6:
            z_score = abs(y - med) / robust_std
            if z_score > recipe.local_outlier_std_devs:
                results[i].append("local_yield_outlier")

    return results
