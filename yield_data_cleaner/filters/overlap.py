# SPDX-License-Identifier: GPL-3.0-or-later
"""Harvest coverage and swath overlap detection filter."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.pass_reconstruction import euclidean_distance, get_point_coordinate
from ..core.recipe import CleaningRecipe


def evaluate_overlap_filter(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Detect harvest overlap where a later pass cuts into previously harvested areas.

    Uses a 2D spatial cell hash to identify points from subsequent passes that fall
    within the harvest footprint of prior passes.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0 or not recipe.filter_overlap:
        return results

    cell_size = max(1.0, recipe.overlap_distance_threshold_m)
    grid: dict[tuple[int, int], list[tuple[int, tuple[float, float], str]]] = {}

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

    for i, obs in enumerate(observations):
        pt = projected_coords[i]
        if pt is None:
            continue

        pass_id = str(obs.get("pass_id") or "unassigned")
        gx = int(math.floor(pt[0] / cell_size))
        gy = int(math.floor(pt[1] / cell_size))

        is_overlap = False

        # Search adjacent cells for points from prior, different passes
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell_key = (gx + dx, gy + dy)
                if cell_key in grid:
                    for prev_idx, prev_pt, prev_pass in grid[cell_key]:
                        # Overlap only against different passes
                        if prev_pass != pass_id:
                            dist = math.hypot(pt[0] - prev_pt[0], pt[1] - prev_pt[1])
                            if dist < recipe.overlap_distance_threshold_m:
                                is_overlap = True
                                break
                if is_overlap:
                    break
            if is_overlap:
                break

        if is_overlap:
            results[i].append("harvest_overlap")

        # Record this point into the spatial grid
        target_cell = (gx, gy)
        if target_cell not in grid:
            grid[target_cell] = []
        grid[target_cell].append((i, pt, pass_id))

    return results
