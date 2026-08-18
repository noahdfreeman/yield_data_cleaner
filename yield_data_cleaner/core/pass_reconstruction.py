# SPDX-License-Identifier: GPL-3.0-or-later
"""Harvest pass reconstruction and validation engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PassReconstructionConfig:
    """Configurable parameters for harvest pass reconstruction."""

    max_time_gap_s: float = 30.0
    max_distance_gap_m: float = 35.0
    turn_angle_threshold_deg: float = 50.0
    min_points_per_pass: int = 3
    split_on_header_disengage: bool = True
    split_on_machine_id: bool = True
    min_pass_length_m: float = 10.0


@dataclass
class PassSegment:
    """A contiguous harvest pass segment."""

    pass_id: str
    pass_source: str  # 'source' or 'reconstructed'
    point_indices: list[int] = field(default_factory=list)
    point_count: int = 0
    start_time: str | None = None
    end_time: str | None = None
    duration_s: float | None = None
    length_m: float = 0.0
    mean_heading_deg: float | None = None
    confidence: float = 1.0
    split_reason: str = "initial"
    line_coords: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_id": self.pass_id,
            "pass_source": self.pass_source,
            "point_count": self.point_count,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": round(self.duration_s, 2) if self.duration_s is not None else None,
            "length_m": round(self.length_m, 2),
            "mean_heading_deg": (
                round(self.mean_heading_deg, 1) if self.mean_heading_deg is not None else None
            ),
            "confidence": round(self.confidence, 3),
            "split_reason": self.split_reason,
            "point_indices": list(self.point_indices),
        }


@dataclass
class PassReconstructionResult:
    """Complete results from pass reconstruction or validation."""

    passes: list[PassSegment] = field(default_factory=list)
    total_passes: int = 0
    mean_pass_length_m: float = 0.0
    mean_pass_duration_s: float = 0.0
    low_confidence_pass_count: int = 0
    split_reason_counts: dict[str, int] = field(default_factory=dict)
    observation_updates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_passes": self.total_passes,
            "mean_pass_length_m": round(self.mean_pass_length_m, 2),
            "mean_pass_duration_s": round(self.mean_pass_duration_s, 2),
            "low_confidence_pass_count": self.low_confidence_pass_count,
            "split_reason_counts": dict(self.split_reason_counts),
            "passes": [p.to_dict() for p in self.passes],
        }


def calculate_bearing(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculate geographic heading/bearing from p1 to p2 in degrees [0, 360)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    bearing = math.degrees(math.atan2(dx, dy))
    return (bearing + 360.0) % 360.0


def heading_difference(h1: float, h2: float) -> float:
    """Compute the absolute smallest angle difference between two headings in [0, 180]."""
    diff = abs(h1 - h2) % 360.0
    return 360.0 - diff if diff > 180.0 else diff


def euclidean_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Compute 2D planar Euclidean distance."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a timestamp into a timezone-aware or naive datetime object."""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def get_point_coordinate(obs: Mapping[str, Any]) -> tuple[float, float] | None:
    """Extract (x, y) coordinate from an observation record."""
    if (
        "geometry" in obs
        and isinstance(obs["geometry"], (tuple, list))
        and len(obs["geometry"]) >= 2
    ):
        try:
            x, y = float(obs["geometry"][0]), float(obs["geometry"][1])
            if math.isfinite(x) and math.isfinite(y):
                return (x, y)
        except (TypeError, ValueError):
            pass

    for x_key, y_key in (
        ("x", "y"),
        ("X", "Y"),
        ("lon", "lat"),
        ("longitude", "latitude"),
        ("easting", "northing"),
    ):
        if x_key in obs and y_key in obs:
            try:
                x_val = obs[x_key]
                y_val = obs[y_key]
                if x_val is not None and y_val is not None:
                    x, y = float(x_val), float(y_val)
                    if math.isfinite(x) and math.isfinite(y):
                        return (x, y)
            except (TypeError, ValueError):
                continue
    return None


def _calculate_mean_heading(headings: Sequence[float]) -> float | None:
    """Calculate circular mean of a sequence of headings in degrees."""
    if not headings:
        return None
    sin_sum = sum(math.sin(math.radians(h)) for h in headings)
    cos_sum = sum(math.cos(math.radians(h)) for h in headings)
    if abs(sin_sum) < 1e-9 and abs(cos_sum) < 1e-9:
        return headings[0]
    mean_rad = math.atan2(sin_sum, cos_sum)
    return (math.degrees(mean_rad) + 360.0) % 360.0


def _calculate_heading_variance(headings: Sequence[float]) -> float:
    """Calculate circular variance [0.0, 1.0] of a sequence of headings."""
    if len(headings) < 2:
        return 0.0
    sin_sum = sum(math.sin(math.radians(h)) for h in headings)
    cos_sum = sum(math.cos(math.radians(h)) for h in headings)
    r = math.hypot(sin_sum, cos_sum) / len(headings)
    return max(0.0, min(1.0, 1.0 - r))


def _finalize_pass(
    segment: PassSegment,
    observations: Sequence[Mapping[str, Any]],
    coords: Sequence[tuple[float, float] | None],
    timestamps: Sequence[datetime | None],
    headings: Sequence[float | None],
    config: PassReconstructionConfig,
) -> None:
    """Compute summary statistics, line geometry, and confidence for a pass segment."""
    segment.point_count = len(segment.point_indices)
    if segment.point_count == 0:
        segment.confidence = 0.0
        return

    first_idx = segment.point_indices[0]
    last_idx = segment.point_indices[-1]

    t_first = timestamps[first_idx]
    t_last = timestamps[last_idx]
    if t_first and t_last and t_last >= t_first:
        segment.start_time = t_first.isoformat()
        segment.end_time = t_last.isoformat()
        segment.duration_s = (t_last - t_first).total_seconds()

    line_pts: list[tuple[float, float]] = []
    total_len = 0.0
    prev_pt: tuple[float, float] | None = None

    valid_headings: list[float] = []

    for idx in segment.point_indices:
        pt = coords[idx]
        if pt is not None:
            line_pts.append(pt)
            if prev_pt is not None:
                total_len += euclidean_distance(prev_pt, pt)
            prev_pt = pt
        h = headings[idx]
        if h is not None and math.isfinite(h):
            valid_headings.append((h + 360.0) % 360.0)

    segment.line_coords = line_pts
    segment.length_m = total_len
    segment.mean_heading_deg = _calculate_mean_heading(valid_headings)

    # Compute confidence score (0.0 to 1.0)
    conf = 1.0

    # Penalize very short point count
    if segment.point_count < config.min_points_per_pass:
        conf *= 0.5

    # Penalize very short spatial length
    if segment.length_m < config.min_pass_length_m and segment.point_count > 1:
        conf *= 0.7

    # Penalize high circular heading variance in a single pass
    if len(valid_headings) >= 3:
        variance = _calculate_heading_variance(valid_headings)
        if variance > 0.35:
            conf *= max(0.4, 1.0 - variance)

    segment.confidence = max(0.0, min(1.0, conf))


def reconstruct_passes(
    observations: Sequence[Mapping[str, Any]],
    config: PassReconstructionConfig | None = None,
) -> PassReconstructionResult:
    """Reconstruct harvest passes from an ordered or unordered sequence of observations.

    Points are sorted by timestamp (or source sequence / index), then segmented
    into contiguous harvest passes using time gaps, distance jumps, heading/turn
    changes, header disengagement, and machine IDs.
    """
    if config is None:
        config = PassReconstructionConfig()

    n = len(observations)
    if n == 0:
        return PassReconstructionResult()

    # Pre-parse timestamps and coordinates
    coords: list[tuple[float, float] | None] = [get_point_coordinate(obs) for obs in observations]
    timestamps: list[datetime | None] = [
        parse_timestamp(obs.get("timestamp_utc")) for obs in observations
    ]

    # Establish sorting order: by timestamp if available, else source_sequence or original index
    def sort_key(idx: int) -> tuple[int, Any, int]:
        ts = timestamps[idx]
        if ts is not None:
            # Sort by datetime (naive or aware converted)
            ts_val = ts.timestamp() if ts.tzinfo else ts.replace(tzinfo=timezone.utc).timestamp()
            return (0, ts_val, idx)
        seq = obs_item.get("source_sequence") if (obs_item := observations[idx]) else None
        if seq is not None:
            try:
                return (1, float(seq), idx)
            except (TypeError, ValueError):
                pass
        return (2, idx, idx)

    sorted_indices = sorted(range(n), key=sort_key)

    # Compute or estimate headings for each point
    headings: list[float | None] = [None] * n
    for i, idx in enumerate(sorted_indices):
        obs = observations[idx]
        h_val = obs.get("heading_deg")
        if h_val is not None:
            try:
                h = float(h_val)
                if math.isfinite(h):
                    headings[idx] = (h + 360.0) % 360.0
                    continue
            except (TypeError, ValueError):
                pass

        # Estimate heading from previous or next point if coordinate exists
        curr_pt = coords[idx]
        if curr_pt is not None:
            if i + 1 < len(sorted_indices):
                next_idx = sorted_indices[i + 1]
                next_pt = coords[next_idx]
                if next_pt is not None and euclidean_distance(curr_pt, next_pt) > 0.5:
                    headings[idx] = calculate_bearing(curr_pt, next_pt)
                    continue
            if i > 0:
                prev_idx = sorted_indices[i - 1]
                prev_pt = coords[prev_idx]
                if prev_pt is not None and euclidean_distance(prev_pt, curr_pt) > 0.5:
                    headings[idx] = calculate_bearing(prev_pt, curr_pt)

    # Segmentation loop
    passes: list[PassSegment] = []
    current_segment: PassSegment | None = None
    pass_number = 1
    split_counts: dict[str, int] = {}

    def start_new_pass(reason: str, initial_idx: int) -> PassSegment:
        nonlocal pass_number
        seg = PassSegment(
            pass_id=str(pass_number),
            pass_source="reconstructed",  # nosec B106
            point_indices=[initial_idx],
            split_reason=reason,
        )
        pass_number += 1
        split_counts[reason] = split_counts.get(reason, 0) + 1
        return seg

    for i, idx in enumerate(sorted_indices):
        obs = observations[idx]
        pt = coords[idx]
        ts = timestamps[idx]
        h = headings[idx]
        mach = str(obs.get("machine_id", "") or "")
        header_engaged = obs.get("header_engaged")

        if current_segment is None:
            current_segment = start_new_pass("initial", idx)
            continue

        prev_idx = current_segment.point_indices[-1]
        prev_obs = observations[prev_idx]
        prev_pt = coords[prev_idx]
        prev_ts = timestamps[prev_idx]
        prev_h = headings[prev_idx]
        prev_mach = str(prev_obs.get("machine_id", "") or "")
        prev_header = prev_obs.get("header_engaged")

        split_reason: str | None = None

        # Check Machine ID split
        if config.split_on_machine_id and mach != prev_mach and (mach or prev_mach):
            split_reason = "machine_change"

        # Check Header Disengagement
        elif config.split_on_header_disengage and prev_header is False and header_engaged is True:
            split_reason = "header_lift"

        # Check Time Gap
        elif ts is not None and prev_ts is not None:
            dt = abs((ts - prev_ts).total_seconds())
            if dt > config.max_time_gap_s:
                split_reason = "time_gap"

        # Check Distance Gap
        if split_reason is None and pt is not None and prev_pt is not None:
            dist = euclidean_distance(prev_pt, pt)
            if dist > config.max_distance_gap_m:
                split_reason = "distance_gap"

        # Check Heading / Turn Change
        if split_reason is None and h is not None and prev_h is not None:
            angle_diff = heading_difference(prev_h, h)
            if angle_diff > config.turn_angle_threshold_deg:
                split_reason = "turn"

        if split_reason is not None:
            _finalize_pass(current_segment, observations, coords, timestamps, headings, config)
            passes.append(current_segment)
            current_segment = start_new_pass(split_reason, idx)
        else:
            current_segment.point_indices.append(idx)

    if current_segment is not None:
        _finalize_pass(current_segment, observations, coords, timestamps, headings, config)
        passes.append(current_segment)

    # Build observation updates list matching original observation indices
    obs_updates: list[dict[str, Any]] = [{} for _ in range(n)]
    low_conf_count = 0
    total_len = 0.0
    total_dur = 0.0
    dur_count = 0

    for seg in passes:
        total_len += seg.length_m
        if seg.duration_s is not None:
            total_dur += seg.duration_s
            dur_count += 1
        if seg.confidence < 0.7:
            low_conf_count += 1

        for idx in seg.point_indices:
            obs_updates[idx] = {
                "pass_id": seg.pass_id,
                "pass_source": seg.pass_source,
                "pass_confidence": seg.confidence,
                "heading_deg": headings[idx],
            }

    mean_len = (total_len / len(passes)) if passes else 0.0
    mean_dur = (total_dur / dur_count) if dur_count else 0.0

    return PassReconstructionResult(
        passes=passes,
        total_passes=len(passes),
        mean_pass_length_m=mean_len,
        mean_pass_duration_s=mean_dur,
        low_confidence_pass_count=low_conf_count,
        split_reason_counts=split_counts,
        observation_updates=obs_updates,
    )


def validate_source_passes(
    observations: Sequence[Mapping[str, Any]],
    config: PassReconstructionConfig | None = None,
) -> PassReconstructionResult:
    """Validate user/monitor-supplied source pass IDs and compute coherence metrics.

    Groups observations by `source_pass_id`, verifying spatial continuity,
    heading consistency, and duration.
    """
    if config is None:
        config = PassReconstructionConfig()

    n = len(observations)
    if n == 0:
        return PassReconstructionResult()

    coords = [get_point_coordinate(obs) for obs in observations]
    timestamps = [parse_timestamp(obs.get("timestamp_utc")) for obs in observations]
    headings: list[float | None] = []
    for obs in observations:
        h_val = obs.get("heading_deg")
        if h_val is not None:
            try:
                h = float(h_val)
                headings.append((h + 360.0) % 360.0 if math.isfinite(h) else None)
                continue
            except (TypeError, ValueError):
                pass
        headings.append(None)

    # Group by source_pass_id preserving order of discovery
    pass_groups: dict[str, list[int]] = {}
    for idx, obs in enumerate(observations):
        pass_id_val = obs.get("source_pass_id")
        if pass_id_val is None or str(pass_id_val).strip() == "":
            pass_id_val = "unassigned"  # nosec B105
        else:
            pass_id_val = str(pass_id_val).strip()
        if pass_id_val not in pass_groups:
            pass_groups[pass_id_val] = []
        pass_groups[pass_id_val].append(idx)

    passes: list[PassSegment] = []
    obs_updates: list[dict[str, Any]] = [{} for _ in range(n)]
    split_counts = {"source": len(pass_groups)}
    low_conf_count = 0
    total_len = 0.0
    total_dur = 0.0
    dur_count = 0

    for pass_id_str, indices in pass_groups.items():
        seg = PassSegment(
            pass_id=pass_id_str,
            pass_source="source",  # nosec B106
            point_indices=indices,
            split_reason="source",
        )
        _finalize_pass(seg, observations, coords, timestamps, headings, config)

        if pass_id_str == "unassigned":  # nosec B105
            seg.confidence = 0.0

        passes.append(seg)
        total_len += seg.length_m
        if seg.duration_s is not None:
            total_dur += seg.duration_s
            dur_count += 1
        if seg.confidence < 0.7:
            low_conf_count += 1

        for idx in indices:
            obs_updates[idx] = {
                "pass_id": seg.pass_id,
                "pass_source": seg.pass_source,
                "pass_confidence": seg.confidence,
                "heading_deg": headings[idx],
            }

    mean_len = (total_len / len(passes)) if passes else 0.0
    mean_dur = (total_dur / dur_count) if dur_count else 0.0

    return PassReconstructionResult(
        passes=passes,
        total_passes=len(passes),
        mean_pass_length_m=mean_len,
        mean_pass_duration_s=mean_dur,
        low_confidence_pass_count=low_conf_count,
        split_reason_counts=split_counts,
        observation_updates=obs_updates,
    )


reconstruct_harvest_passes = reconstruct_passes
