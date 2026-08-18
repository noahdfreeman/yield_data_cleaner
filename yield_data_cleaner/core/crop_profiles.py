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

    @property
    def test_weight_lb_per_bu(self) -> float:
        return self.test_weight_lb_per_bushel


CROP_PROFILES = {
    "corn": CropProfile("corn", "Corn", 15.5, 56.0),
    "soybean": CropProfile("soybean", "Soybean", 13.0, 60.0),
    "wheat": CropProfile("wheat", "Wheat", 13.5, 60.0),
    "barley": CropProfile("barley", "Barley", 14.5, 48.0),
    "oats": CropProfile("oats", "Oats", 14.0, 32.0),
    "sorghum": CropProfile("sorghum", "Sorghum / Milo", 14.0, 56.0),
    "canola": CropProfile("canola", "Canola / Rapeseed", 10.0, 50.0),
    "sunflower": CropProfile("sunflower", "Sunflower", 10.0, 28.0),
}


def available_crops() -> list[CropProfile]:
    return list(CROP_PROFILES.values())


def crop_profile(code: str) -> CropProfile:
    key = str(code).strip().lower()
    try:
        return CROP_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported crop: {code!r}") from exc


def detect_crop_code(source_text: str, rows: list = None) -> str | None:
    """Auto-detect crop code from filename, layer name, or attribute values."""
    if not source_text:
        source_text = ""
    lower = source_text.lower()

    # 1. Check direct keywords in source_text (filename, layer name, path)
    if any(k in lower for k in ("soybean", "soybeans", "soya", "beans", "bean")):
        return "soybean"
    if any(k in lower for k in ("corn", "maize")):
        return "corn"
    if any(k in lower for k in ("wheat", "wht")):
        return "wheat"
    if "barley" in lower:
        return "barley"
    if any(k in lower for k in ("oats", "oat")):
        return "oats"
    if any(k in lower for k in ("sorghum", "milo")):
        return "sorghum"
    if any(k in lower for k in ("canola", "rapeseed")):
        return "canola"
    if any(k in lower for k in ("sunflower", "sunflowers")):
        return "sunflower"

    # 2. Check sample rows for crop / product / commodity / grain fields
    if rows:
        for r in rows[:50]:
            if not isinstance(r, dict):
                continue
            for col_name, val in r.items():
                if val is not None and any(
                    term in col_name.lower()
                    for term in ("crop", "prod", "comm", "type", "grain", "hybrid")
                ):
                    val_str = str(val).lower()
                    if any(k in val_str for k in ("soybean", "soybeans", "soya", "beans", "bean")):
                        return "soybean"
                    if any(k in val_str for k in ("corn", "maize")):
                        return "corn"
                    if any(k in val_str for k in ("wheat", "wht")):
                        return "wheat"
                    if "barley" in val_str:
                        return "barley"
                    if any(k in val_str for k in ("oats", "oat")):
                        return "oats"
                    if any(k in val_str for k in ("sorghum", "milo")):
                        return "sorghum"
                    if any(k in val_str for k in ("canola", "rapeseed")):
                        return "canola"
                    if any(k in val_str for k in ("sunflower", "sunflowers")):
                        return "sunflower"
    return None
