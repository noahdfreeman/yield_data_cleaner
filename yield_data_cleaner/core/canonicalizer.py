# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert mapped source attributes into canonical observation values."""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, time, timezone
from typing import Any, Mapping

from .canonical_schema import CleanStatus, CrsConfidence
from .crop_profiles import crop_profile
from .mapping_profile import MappingProfile
from .units import (
    adjust_yield_for_moisture,
    bushels_per_acre_to_kg_per_hectare,
    mph_to_m_s,
    pounds_per_acre_to_kg_per_hectare,
)

POUNDS_TO_KG = 0.45359237
FEET_TO_METERS = 0.3048
KM_PER_HOUR_TO_M_PER_S = 1.0 / 3.6

NUMERIC_MEASUREMENTS = {
    "yield_wet_mass_area",
    "yield_dry_mass_area",
    "mass_flow_wet",
    "mass_flow_dry",
    "moisture_pct",
    "speed_m_s",
    "distance_m",
    "duration_s",
    "swath_width_m",
    "heading_deg",
    "elevation_m",
    "pass_confidence",
}


def stable_observation_id(source_name: str, source_index: int) -> str:
    value = f"{source_name}\0{int(source_index)}".encode("utf-8", errors="surrogatepass")
    return f"obs_{hashlib.sha256(value).hexdigest()[:20]}"


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _boolean(value: Any) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "down", "engaged", "recording"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "up", "disengaged", "not recording"}:
        return False
    return None


def _timestamp(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return str(value).strip()
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _combined_timestamp(date_value: Any, time_value: Any) -> str | None:
    if date_value in (None, "") or time_value in (None, ""):
        return None
    if isinstance(date_value, date):
        date_text = date_value.isoformat()
    else:
        date_text = str(date_value).strip()
    if isinstance(time_value, time):
        time_text = time_value.isoformat()
    else:
        time_text = str(time_value).strip()
    return _timestamp(f"{date_text}T{time_text}")


def _source_unit(field_name: str, profile: MappingProfile) -> str:
    override = profile.source_units.get(field_name)
    if override:
        return override.strip().lower().replace(" ", "").replace("_", "")
    if field_name in {"yield_wet_mass_area", "yield_dry_mass_area"}:
        return "bu/ac" if profile.unit_profile == "imperial" else "kg/ha"
    if field_name in {"mass_flow_wet", "mass_flow_dry"}:
        return "lb/s" if profile.unit_profile == "imperial" else "kg/s"
    if field_name == "speed_m_s":
        return "mph" if profile.unit_profile == "imperial" else "km/h"
    if field_name in {"distance_m", "swath_width_m", "elevation_m"}:
        return "ft" if profile.unit_profile == "imperial" else "m"
    return "canonical"


def _canonical_number(field_name: str, value: Any, profile: MappingProfile) -> float | None:
    number = _number(value)
    if number is None:
        return None
    unit = _source_unit(field_name, profile)
    if field_name in {"yield_wet_mass_area", "yield_dry_mass_area"}:
        if unit in {"bu/ac", "buacre", "bushel/acre", "bushels/acre"}:
            crop = crop_profile(profile.crop_code)
            return bushels_per_acre_to_kg_per_hectare(number, crop.test_weight_lb_per_bushel)
        if unit in {"lb/ac", "lb/acre", "lbs/ac", "lbs/acre", "pound/acre", "pounds/acre"}:
            return pounds_per_acre_to_kg_per_hectare(number)
        if unit in {"tonne/ha", "t/ha", "ton/ha", "tonnes/ha"}:
            return number * 1000.0
        if unit in {"kg/ha", "kgha", "canonical"}:
            return number
    if field_name == "moisture_pct":
        if unit in {"fraction", "0-1", "0_1", "ratio"}:
            return number * 100.0
        return number
    if field_name in {"mass_flow_wet", "mass_flow_dry"}:
        if unit in {"lb/s", "lbs", "lbsec"}:
            return number * POUNDS_TO_KG
        if unit in {"kg/s", "kgs", "canonical"}:
            return number
    if field_name == "speed_m_s":
        if unit in {"mph", "miles/hr", "miles/hour"}:
            return mph_to_m_s(number)
        if unit in {"km/h", "kph", "kmh"}:
            return number * KM_PER_HOUR_TO_M_PER_S
        if unit in {"m/s", "mps", "canonical"}:
            return number
    if field_name in {"distance_m", "swath_width_m", "elevation_m"}:
        if unit in {"ft", "feet", "foot"}:
            return number * FEET_TO_METERS
        if unit in {"in", "inch", "inches"}:
            return number * 0.0254
        if unit in {"cm", "centimeter", "centimeters"}:
            return number * 0.01
        if unit in {"rows30in", "rows(30in)", "rows(30in/row)"}:
            return number * (30.0 * 0.0254)
        if unit in {"m", "meter", "metre", "canonical"}:
            return number
    return number


def canonicalize_attributes(
    source_attributes: Mapping[str, Any],
    source_name: str,
    source_index: int,
    profile: MappingProfile,
    analysis_crs: str | None = None,
    crs_confidence: CrsConfidence = CrsConfidence.UNRESOLVED,
) -> dict[str, Any]:
    """Return canonical values while leaving source attributes untouched."""

    errors = profile.validate(list(source_attributes))
    if errors:
        raise ValueError("; ".join(errors))
    mapping = profile.mapping

    def source_value(canonical: str) -> Any:
        column = mapping.get(canonical)
        return source_attributes.get(column) if column else None

    timestamp = _timestamp(source_value("timestamp_utc"))
    if timestamp is None:
        timestamp = _combined_timestamp(source_value("date"), source_value("time"))
    sequence = _number(source_value("source_sequence"))

    result: dict[str, Any] = {
        "observation_id": stable_observation_id(source_name, source_index),
        "source_index": int(source_index),
        "source_name": source_name,
        "timestamp_utc": timestamp,
        "source_sequence": int(sequence) if sequence is not None else int(source_index),
        "crop_code": profile.crop_code,
        "unit_profile": profile.unit_profile,
        "source_crs": profile.source_crs,
        "analysis_crs": analysis_crs,
        "crs_confidence": crs_confidence.value,
        "clean_status": CleanStatus.UNAVAILABLE.value,
        "filter_flags": "",
        "filter_reasons": "",
        "manual_action": "none",
        "boundary_status": "unavailable",
    }
    for field_name in NUMERIC_MEASUREMENTS:
        result[field_name] = _canonical_number(field_name, source_value(field_name), profile)
    result["header_engaged"] = _boolean(source_value("header_engaged"))
    for field_name in ("machine_id", "source_pass_id", "pass_id", "pass_source"):
        value = source_value(field_name)
        result[field_name] = None if value is None or str(value).strip() == "" else str(value)
    if not result.get("pass_id") and result.get("source_pass_id"):
        result["pass_id"] = result["source_pass_id"]
        result["pass_source"] = "source"

    # Yield Calculation Precedence:
    # 1. Primary: If physical sensor calculation variables (mass flow, speed, swath width) are available,
    # calculate yield dynamically from flow rate and area rate.
    flow_kg_s = result.get("mass_flow_wet")
    spd_m_s = result.get("speed_m_s")
    width_m = result.get("swath_width_m")
    crop = crop_profile(profile.crop_code)
    std_moist = crop.standard_moisture_pct
    m_pct = result.get("moisture_pct")

    calculated_dry_yield = None
    if flow_kg_s and spd_m_s and width_m and flow_kg_s > 0 and spd_m_s > 0 and width_m > 0:
        area_rate = spd_m_s * width_m
        wet_kg_ha = (flow_kg_s / area_rate) * 10000.0
        if result.get("yield_wet_mass_area") is None:
            result["yield_wet_mass_area"] = wet_kg_ha
        if m_pct is not None and 0 <= m_pct < 100:
            try:
                calculated_dry_yield = adjust_yield_for_moisture(wet_kg_ha, m_pct, std_moist)
            except Exception:
                calculated_dry_yield = wet_kg_ha
        else:
            calculated_dry_yield = wet_kg_ha

    if calculated_dry_yield is not None:
        result["yield_dry_mass_area"] = calculated_dry_yield
    elif result.get("yield_dry_mass_area") is None:
        # 2. Fallback: If calculation attributes were missing or zero, use direct wet or direct dry yield
        wet_y = result.get("yield_wet_mass_area")
        if wet_y is not None and wet_y > 0:
            if m_pct is not None and 0 <= m_pct < 100:
                try:
                    result["yield_dry_mass_area"] = adjust_yield_for_moisture(
                        wet_y, m_pct, std_moist
                    )
                except Exception:
                    result["yield_dry_mass_area"] = wet_y
            else:
                result["yield_dry_mass_area"] = wet_y

    return result
