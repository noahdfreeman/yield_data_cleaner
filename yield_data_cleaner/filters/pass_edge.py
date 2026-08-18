# SPDX-License-Identifier: GPL-3.0-or-later
"""Pass-edge (start and end of pass) latency filters."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..core.recipe import CleaningRecipe


def evaluate_pass_edge_filters(
    observations: Sequence[Mapping[str, Any]],
    recipe: CleaningRecipe,
) -> list[list[str]]:
    """Flag start-of-pass and end-of-pass observations to account for elevator fill/empty latency.

    Returns a list of reason code lists matching observation indices.
    """
    n = len(observations)
    results: list[list[str]] = [[] for _ in range(n)]
    if n == 0:
        return results

    if not recipe.filter_pass_start and not recipe.filter_pass_end:
        return results

    # Group by pass_id
    pass_groups: dict[str, list[int]] = {}
    for i, obs in enumerate(observations):
        pass_id = str(obs.get("pass_id") or "unassigned")
        if pass_id not in pass_groups:
            pass_groups[pass_id] = []
        pass_groups[pass_id].append(i)

    for pass_id, indices in pass_groups.items():
        if pass_id == "unassigned" or not indices:
            continue

        count = len(indices)
        if count <= 2:
            continue

        # Flag start of pass
        if recipe.filter_pass_start and recipe.pass_start_count > 0:
            start_k = min(recipe.pass_start_count, count // 2)
            for idx in indices[:start_k]:
                results[idx].append("pass_start")

        # Flag end of pass
        if recipe.filter_pass_end and recipe.pass_end_count > 0:
            end_k = min(recipe.pass_end_count, count // 2)
            for idx in indices[max(0, count - end_k) :]:
                results[idx].append("pass_end")

    return results
