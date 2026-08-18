# SPDX-License-Identifier: GPL-3.0-or-later
"""Harvest coverage polygon and swath footprint builder."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..core.pass_reconstruction import get_point_coordinate


@dataclass
class SwathFootprint:
    """A rectangular swath footprint polygon for an individual observation."""

    observation_id: str
    pass_id: str
    coordinates: list[tuple[float, float]] = field(default_factory=list)
    area_m2: float = 0.0
    swath_width_m: float = 6.0
    length_m: float = 2.0
    yield_wet_mass_area: float | None = None

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [self.coordinates],
            },
            "properties": {
                "observation_id": self.observation_id,
                "pass_id": self.pass_id,
                "area_m2": round(self.area_m2, 2),
                "swath_width_m": round(self.swath_width_m, 2),
                "length_m": round(self.length_m, 2),
                "yield_wet_mass_area": (
                    round(self.yield_wet_mass_area, 2)
                    if self.yield_wet_mass_area is not None
                    else None
                ),
            },
        }


def build_swath_footprint(
    x: float,
    y: float,
    heading_deg: float,
    swath_width_m: float,
    length_m: float,
    obs_id: str = "",
    pass_id: str = "",
    yield_val: float | None = None,
) -> SwathFootprint:
    """Construct a 4-point rectangular footprint oriented along the travel heading."""
    w_half = max(0.5, swath_width_m / 2.0)
    l_half = max(0.5, length_m / 2.0)

    # Travel vector: heading 0=North (+Y), 90=East (+X)
    h_rad = math.radians(heading_deg % 360.0)
    fwd_x = math.sin(h_rad) * l_half
    fwd_y = math.cos(h_rad) * l_half

    # Perpendicular right vector: heading + 90 deg
    perp_x = math.cos(h_rad) * w_half
    perp_y = -math.sin(h_rad) * w_half

    c1 = (round(x - perp_x - fwd_x, 3), round(y - perp_y - fwd_y, 3))
    c2 = (round(x - perp_x + fwd_x, 3), round(y - perp_y + fwd_y, 3))
    c3 = (round(x + perp_x + fwd_x, 3), round(y + perp_y + fwd_y, 3))
    c4 = (round(x + perp_x - fwd_x, 3), round(y + perp_y - fwd_y, 3))

    return SwathFootprint(
        observation_id=obs_id,
        pass_id=pass_id,
        coordinates=[c1, c2, c3, c4, c1],
        area_m2=swath_width_m * length_m,
        swath_width_m=swath_width_m,
        length_m=length_m,
        yield_wet_mass_area=yield_val,
    )


def build_pass_coverage_footprints(
    observations: Sequence[Mapping[str, Any]],
    default_swath_width_m: float = 6.0,
    default_length_m: float = 2.0,
) -> list[SwathFootprint]:
    """Generate swath footprints for all valid observations in a dataset."""
    coords = [get_point_coordinate(obs) for obs in observations]
    footprints: list[SwathFootprint] = []

    for i, obs in enumerate(observations):
        pt = coords[i]
        if pt is None:
            continue

        w_val = obs.get("swath_width_m")
        try:
            w = float(w_val) if w_val is not None and float(w_val) > 0 else default_swath_width_m
        except (TypeError, ValueError):
            w = default_swath_width_m

        h_val = obs.get("heading_deg")
        try:
            h = float(h_val) if h_val is not None else 0.0
        except (TypeError, ValueError):
            h = 0.0

        # Estimate length from distance or speed * duration
        dist_val = obs.get("distance_m")
        try:
            dist = (
                float(dist_val)
                if dist_val is not None and float(dist_val) > 0
                else default_length_m
            )
        except (TypeError, ValueError):
            dist = default_length_m

        y_val = obs.get("yield_wet_mass_area")
        yield_num = float(y_val) if y_val is not None else None

        fp = build_swath_footprint(
            x=pt[0],
            y=pt[1],
            heading_deg=h,
            swath_width_m=w,
            length_m=dist,
            obs_id=str(obs.get("observation_id", i)),
            pass_id=str(obs.get("pass_id", "1")),
            yield_val=yield_num,
        )
        footprints.append(fp)

    return footprints
