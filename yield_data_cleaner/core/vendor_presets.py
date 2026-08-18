# SPDX-License-Identifier: GPL-3.0-or-later
"""Built-in vendor mapping presets for common harvest monitor text exports."""

from __future__ import annotations

from typing import Sequence

from .mapping_profile import MappingProfile

AGLEADER_MAPPING = {
    "x": "Longitude",
    "y": "Latitude",
    "timestamp_utc": "Time",
    "yield_wet_mass_area": "Yield (bu/ac)",
    "moisture_pct": "Moisture (%)",
    "speed_m_s": "Speed (mph)",
    "swath_width_m": "Width (ft)",
    "heading_deg": "Heading",
    "elevation_m": "Elevation (ft)",
    "source_pass_id": "Pass",
}

GREENSTAR_MAPPING = {
    "x": "LONGITUDE",
    "y": "LATITUDE",
    "timestamp_utc": "DATE_TIME",
    "yield_wet_mass_area": "DRY_YIELD",
    "moisture_pct": "MOISTURE",
    "speed_m_s": "SPEED",
    "swath_width_m": "SWATH_WIDTH",
    "heading_deg": "HEADING",
    "elevation_m": "ELEVATION",
    "source_pass_id": "PASS_NUM",
}

VENDOR_SOURCE_UNITS = {
    "yield_wet_mass_area": "bu/ac",
    "speed_m_s": "mph",
    "swath_width_m": "ft",
    "elevation_m": "ft",
}


def get_vendor_preset(
    preset_name: str,
    crop_code: str = "corn",
    unit_profile: str = "imperial",
) -> MappingProfile:
    """Return a configured MappingProfile for the specified vendor preset."""
    name_norm = preset_name.strip().lower()
    if "greenstar" in name_norm or "deere" in name_norm or "john" in name_norm:
        return MappingProfile(
            profile_name="John Deere / GreenStar Text",
            crop_code=crop_code,
            unit_profile=unit_profile,
            mapping=dict(GREENSTAR_MAPPING),
            source_units=dict(VENDOR_SOURCE_UNITS),
            source_crs="EPSG:4326",
        )

    # Default Ag Leader
    return MappingProfile(
        profile_name="Ag Leader Text",
        crop_code=crop_code,
        unit_profile=unit_profile,
        mapping=dict(AGLEADER_MAPPING),
        source_units=dict(VENDOR_SOURCE_UNITS),
        source_crs="EPSG:4326",
    )


def match_vendor_preset(headers: Sequence[str]) -> str | None:
    """Detect if headers closely match a recognized vendor preset."""
    norm_headers = {str(h).strip().lower() for h in headers}

    # Check Ag Leader signatures
    agleader_sigs = {
        "yield (bu/ac)",
        "yield(bu/ac)",
        "moisture (%)",
        "moisture(%)",
        "speed (mph)",
        "width (ft)",
    }
    if sum(1 for s in agleader_sigs if s in norm_headers) >= 2:
        return "agleader"

    # Check GreenStar signatures
    greenstar_sigs = {"dry_yield", "wet_mass", "swath_width", "pass_num", "date_time", "track_deg"}
    if sum(1 for s in greenstar_sigs if s in norm_headers) >= 2:
        return "greenstar"

    return None
