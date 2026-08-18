# SPDX-License-Identifier: GPL-3.0-or-later
"""Sensor flow and moisture delay estimation and correction."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from ..core.pass_reconstruction import parse_timestamp


@dataclass
class DelayEstimationResult:
    """Diagnostic outcome of automatic delay estimation."""

    estimated_delay_s: float
    confidence: float
    is_stable: bool
    candidate_scores: dict[float, float] = field(default_factory=dict)
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_delay_s": round(self.estimated_delay_s, 2),
            "confidence": round(self.confidence, 3),
            "is_stable": self.is_stable,
            "candidate_scores": {str(k): round(v, 4) for k, v in self.candidate_scores.items()},
            "evidence": self.evidence,
        }


def apply_sensor_delays(
    observations: Sequence[Mapping[str, Any]],
    flow_delay_s: float = 0.0,
    moisture_delay_s: float = 0.0,
) -> list[dict[str, Any]]:
    """Shift flow/yield and moisture values along chronological points within each pass.

    The combine grain elevator introduces transport latency: grain cut at position P(t)
    reaches the flow sensor at time t + delay. This correction assigns the sensor reading
    from time t + delay back to the observation at position P(t).
    """
    n = len(observations)
    if n == 0 or (flow_delay_s <= 0.0 and moisture_delay_s <= 0.0):
        return [dict(obs) for obs in observations]

    timestamps: list[datetime | None] = [
        parse_timestamp(obs.get("timestamp_utc")) for obs in observations
    ]
    adjusted_obs: list[dict[str, Any]] = [dict(obs) for obs in observations]

    # Group by pass_id
    pass_groups: dict[str, list[int]] = {}
    for i, obs in enumerate(observations):
        pass_id = str(obs.get("pass_id") or "unassigned")
        if pass_id not in pass_groups:
            pass_groups[pass_id] = []
        pass_groups[pass_id].append(i)

    flow_fields = ("yield_wet_mass_area", "yield_dry_mass_area", "mass_flow_wet", "mass_flow_dry")

    for pass_id, indices in pass_groups.items():
        if pass_id == "unassigned" or len(indices) < 2:  # nosec B105
            continue

        # Estimate average sampling interval within pass
        dts: list[float] = []
        for k in range(1, len(indices)):
            t_curr = timestamps[indices[k]]
            t_prev = timestamps[indices[k - 1]]
            if t_curr and t_prev:
                dt = (t_curr - t_prev).total_seconds()
                if 0.1 <= dt <= 10.0:
                    dts.append(dt)

        interval = (sum(dts) / len(dts)) if dts else 1.0
        flow_shift = max(0, int(round(flow_delay_s / interval))) if flow_delay_s > 0 else 0
        moist_shift = max(0, int(round(moisture_delay_s / interval))) if moisture_delay_s > 0 else 0

        # Apply flow shift
        if flow_shift > 0:
            for k in range(len(indices)):
                target_idx = indices[k]
                source_k = k + flow_shift
                if source_k < len(indices):
                    source_idx = indices[source_k]
                    for f in flow_fields:
                        adjusted_obs[target_idx][f] = observations[source_idx].get(f)
                else:
                    # End of pass where future sensor reading is unavailable
                    for f in flow_fields:
                        adjusted_obs[target_idx][f] = None

        # Apply moisture shift
        if moist_shift > 0:
            for k in range(len(indices)):
                target_idx = indices[k]
                source_k = k + moist_shift
                if source_k < len(indices):
                    source_idx = indices[source_k]
                    adjusted_obs[target_idx]["moisture_pct"] = observations[source_idx].get(
                        "moisture_pct"
                    )
                else:
                    adjusted_obs[target_idx]["moisture_pct"] = None

    return adjusted_obs


def estimate_flow_delay(
    observations: Sequence[Mapping[str, Any]],
    candidate_delays: Sequence[float] = (4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0),
) -> DelayEstimationResult:
    """Estimate optimal flow delay by evaluating cross-pass variance minimization.

    Compares candidate delays and checks curve stability.
    """
    n = len(observations)
    if n < 20:
        return DelayEstimationResult(
            estimated_delay_s=12.0,
            confidence=0.3,
            is_stable=False,
            evidence="Insufficient observations for reliable delay optimization (<20 points)",
        )

    # Calculate variance score for each candidate delay
    scores: dict[float, float] = {}
    for delay in candidate_delays:
        shifted = apply_sensor_delays(observations, flow_delay_s=delay)
        yield_vals = [
            y
            for obs in shifted
            if (y_val := obs.get("yield_wet_mass_area")) is not None
            and (y := float(y_val)) > 0
            and math.isfinite(y)
        ]
        if len(yield_vals) >= 10:
            mean = sum(yield_vals) / len(yield_vals)
            var = sum((v - mean) ** 2 for v in yield_vals) / len(yield_vals)
            scores[delay] = var
        else:
            scores[delay] = float("inf")

    valid_scores = {k: v for k, v in scores.items() if math.isfinite(v)}
    if not valid_scores:
        return DelayEstimationResult(
            estimated_delay_s=12.0,
            confidence=0.3,
            is_stable=False,
            candidate_scores=scores,
            evidence="No valid candidate delay scores could be computed",
        )

    best_delay = min(valid_scores.keys(), key=lambda k: valid_scores[k])
    min_score = valid_scores[best_delay]
    max_score = max(valid_scores.values())

    score_range = max_score - min_score
    relative_depth = (score_range / max_score) if max_score > 0 else 0.0

    is_stable = relative_depth > 0.05
    confidence = min(1.0, max(0.2, relative_depth * 4.0))

    evidence = (
        f"Optimal candidate delay {best_delay}s with relative variance depth {round(relative_depth * 100.0, 1)}%"
        if is_stable
        else f"Unstable delay curve (flat variance profile, {round(relative_depth * 100.0, 1)}% depth)"
    )

    return DelayEstimationResult(
        estimated_delay_s=best_delay,
        confidence=confidence,
        is_stable=is_stable,
        candidate_scores=scores,
        evidence=evidence,
    )
