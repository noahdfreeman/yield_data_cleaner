# SPDX-License-Identifier: GPL-3.0-or-later
"""Crop-specific market moisture and bushel conversion assumptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CropProfile:
    code: str
    display_name: str
    standard_moisture_pct: float
    test_weight_lb_per_bushel: float


CROP_PROFILES = {
    "corn": CropProfile("corn", "Corn", 15.5, 56.0),
    "soybean": CropProfile("soybean", "Soybean", 13.0, 60.0),
    "wheat": CropProfile("wheat", "Wheat", 13.5, 60.0),
}


def crop_profile(code: str) -> CropProfile:
    key = str(code).strip().lower()
    try:
        return CROP_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported crop: {code!r}") from exc
