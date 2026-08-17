# SPDX-License-Identifier: GPL-3.0-or-later
"""Input quality and geometry integrity filters."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..core.pass_reconstruction import euclidean_distance, get_point_coordinate, parse_timestamp
from ..core.recipe import CleaningRecipe


def evaluate_quality_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Evaluate geometry, numeric validity, duplicate, and position jump filters.

    Returns a list of reason code lists matching observation indices.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0:
        return results

    coords = [get_point_coordinate(obs) for obs in observations]
    timestamps = [parse_timestamp(obs.get("timestamp_utc")) for obs in observations]

    seen_signatures: dict[tuple[float, float, str], int] = {}

    for i, obs in enumerate(observations):
        pt = coords[i]
        ts = timestamps[i]

        # Check geometry
        if recipe.check_geometry:
            if pt is None or not math.isfinite(pt[0]) or not math.isfinite(pt[1]):
                results[i].append("invalid_geometry")

        # Check numeric validity of primary yield fields
        if recipe.check_numeric:
            yield_val = None
            for k in ("yield_dry_mass_area", "yield_wet_mass_area", "dry_yield_mass_area", "yield"):
                val = obs.get(k)
                if val is not None:
                    yield_val = val
                    break
            if yield_val is not None:
                try:
                    num = float(yield_val)
                    if not math.isfinite(num) or num < 0:
                        results[i].append("invalid_numeric")
                except (TypeError, ValueError):
                    results[i].append("invalid_numeric")

        # Check duplicates (matching position & timestamp)
        if recipe.check_duplicates and pt is not None and ts is not None:
            sig = (round(pt[0], 4), round(pt[1], 4), ts.isoformat())
            if sig in seen_signatures:
                results[i].append("duplicate_observation")
            else:
                seen_signatures[sig] = i

    # Group by pass_id to evaluate within-pass position jumps and timestamp monotonicity
    pass_groups: dict[str, list[int]] = {}
    for i, obs in enumerate(observations):
        pass_id = str(obs.get("pass_id") or "unassigned")
        if pass_id not in pass_groups:
            pass_groups[pass_id] = []
        pass_groups[pass_id].append(i)

    for pass_id, indices in pass_groups.items():
        if pass_id == "unassigned" or len(indices) < 2:
            continue

        for k in range(1, len(indices)):
            curr_idx = indices[k]
            prev_idx = indices[k - 1]

            # Timestamp order
            if recipe.check_timestamp_order:
                t_curr = timestamps[curr_idx]
                t_prev = timestamps[prev_idx]
                if t_curr and t_prev and t_curr < t_prev:
                    results[curr_idx].append("invalid_timestamp")

            # Position jump
            if recipe.check_position_jumps:
                pt_curr = coords[curr_idx]
                pt_prev = coords[prev_idx]
                if pt_curr and pt_prev:
                    dist = euclidean_distance(pt_prev, pt_curr)
                    if dist > recipe.max_position_jump_m:
                        results[curr_idx].append("position_jump")

    return results
