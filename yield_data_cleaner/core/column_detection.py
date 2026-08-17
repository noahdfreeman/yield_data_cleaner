# SPDX-License-Identifier: GPL-3.0-or-later
"""Explainable column-name suggestions for common yield-monitor exports."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "x": ("longitude", "lon", "long", "x", "xcoord", "xcoordinate", "easting", "east", "gps_lon", "long_dd"),
    "y": ("latitude", "lat", "y", "ycoord", "ycoordinate", "northing", "north", "gps_lat", "lat_dd"),
    "timestamp_utc": ("timestamp", "datetime", "dateandtime", "gpsdatetime", "gpstime", "utc", "iso_time", "dt_utc"),
    "date": ("date", "harvestdate", "gpsdate", "harvest_date", "day"),
    "time": ("time", "harvesttime", "localtime", "harvest_time", "tod"),
    "source_sequence": (
        "objid",
        "obj_id",
        "objectid",
        "pointid",
        "recordid",
        "record_id",
        "rec_id",
        "sequence",
        "seq",
        "record",
        "index",
        "id",
        "fid",
        "point_num",
    ),
    "source_pass_id": (
        "passnum",
        "pass_num",
        "passnumber",
        "passno",
        "passid",
        "pass_id",
        "pass",
        "tracknum",
        "track_num",
        "trackid",
        "track_id",
        "swathnum",
        "swathid",
        "loadid",
        "swath_id",
    ),
    "yield_dry_mass_area": (
        "yldvoldr",
        "yld_vol_dr",
        "yieldvoldry",
        "dryyield",
        "yielddry",
        "dry_yield",
        "yield_dry",
        "yield",
        "yieldbuac",
        "dryyieldbuac",
        "yieldvolume",
        "dry_yld",
        "yld_dry",
        "dry_bu_ac",
        "dry_kg_ha",
        "dry_lb_ac",
        "yldmassd",
        "yld_mass_d",
        "yieldmassdry",
    ),
    "yield_wet_mass_area": (
        "yldvolwe",
        "yld_vol_we",
        "yieldvolwet",
        "wetyield",
        "yieldwet",
        "wet_yield",
        "yield_wet",
        "wet_bu_ac",
        "wet_kg_ha",
        "wet_lb_ac",
        "yldmassw",
        "yld_mass_w",
        "yieldmasswet",
        "wetmassyield",
        "wetyieldmass",
        "wet_yld",
        "yld_wet",
    ),
    "mass_flow_wet": (
        "cropflwm",
        "crop_flw_m",
        "cropflwv",
        "crop_flw_v",
        "massflow",
        "mass_flow",
        "wetmassflow",
        "wet_mass_flow",
        "flow",
        "flowrate",
        "flow_rate",
        "grainflow",
        "grain_flow",
        "grainflowwet",
        "flwmass",
        "flwvol",
        "crop_flow",
    ),
    "mass_flow_dry": (
        "drymassflow",
        "dry_mass_flow",
        "grainflowdry",
        "grain_flow_dry",
        "dryflow",
        "flowdry",
        "flow_dry",
    ),
    "moisture_pct": (
        "moisture",
        "moisturepct",
        "moist",
        "grainmoisture",
        "grain_moist",
        "cropmoisture",
        "crop_moist",
        "mst",
        "pctmoisture",
        "moisture_pct",
        "moisture__",
        "moisture_",
        "grain_mst",
    ),
    "speed_m_s": (
        "speedmph",
        "speed_mph",
        "speedkph",
        "speed_kph",
        "speedmps",
        "speed_mps",
        "speed",
        "groundspeed",
        "ground_speed",
        "velocity",
        "gpsspeed",
        "gps_speed",
        "spd",
        "speed_mph_",
    ),
    "distance_m": (
        "distancef",
        "distance_f",
        "distancem",
        "distance_m",
        "distance",
        "traveldistance",
        "travel_distance",
        "dist",
        "distanceft",
        "dist_ft",
        "dist_m",
        "distft",
        "distm",
        "distance_f_",
    ),
    "duration_s": (
        "durations",
        "duration_s",
        "duration",
        "seconds",
        "interval",
        "elapsedtime",
        "elapsed_time",
        "timesec",
        "time_s",
        "dursec",
        "duration_s_",
    ),
    "swath_width_m": (
        "swthwdth",
        "swth_wdth",
        "swthwdth_",
        "swth_wdth_",
        "swathwidth",
        "swath_width",
        "swath",
        "headerwidth",
        "header_width",
        "width",
        "cutwidth",
        "cut_width",
        "effectivewidth",
        "effective_width",
        "swath_ft",
        "swath_m",
    ),
    "heading_deg": (
        "trackdeg",
        "track_deg",
        "trackdeg_",
        "track_deg_",
        "heading",
        "bearing",
        "trackangle",
        "track_angle",
        "direction",
        "course",
        "headdeg",
        "track",
    ),
    "header_engaged": (
        "workstate",
        "work_state",
        "workstatus",
        "work_status",
        "headerstatus",
        "header_status",
        "header",
        "headerdown",
        "header_down",
        "engaged",
        "implementstatus",
        "implement_status",
        "recording",
        "working",
    ),
    "elevation_m": (
        "elevation",
        "altitude",
        "height",
        "gpsaltitude",
        "gps_elev",
        "elev",
        "elev_m",
        "elev_ft",
        "elevation_",
        "elevation_m",
        "elevation_ft",
    ),
    "crop_code": ("product", "crop", "croptype", "crop_type", "commodity", "harvestedcrop", "crop_name"),
    "machine_id": ("machine", "machineid", "machine_id", "combine", "combine_id", "device", "deviceid", "serialnumber", "serial_num"),
}

NUMERIC_FIELDS = {
    "x",
    "y",
    "source_sequence",
    "yield_dry_mass_area",
    "yield_wet_mass_area",
    "mass_flow_wet",
    "mass_flow_dry",
    "moisture_pct",
    "speed_m_s",
    "distance_m",
    "duration_s",
    "swath_width_m",
    "heading_deg",
    "elevation_m",
}


@dataclass(frozen=True)
class MappingSuggestion:
    canonical_field: str
    source_column: str
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _nonempty(values: Iterable[object]) -> list[object]:
    return [value for value in values if value is not None and str(value).strip() != ""]


def _numeric_ratio(values: Iterable[object]) -> float:
    candidates = _nonempty(values)
    if not candidates:
        return 0.0
    valid = 0
    for value in candidates:
        try:
            number = float(str(value).replace(",", ""))
            valid += int(math.isfinite(number))
        except (TypeError, ValueError):
            pass
    return valid / len(candidates)


def _name_score(column: str, alias: str) -> float:
    normalized = normalize_name(column)
    target = normalize_name(alias)
    if not normalized or not target:
        return 0.0
    if normalized == target:
        return 0.98
    if target in normalized and len(target) >= 3:
        return 0.88
    if normalized in target and len(normalized) >= 3:
        return 0.82
    return 0.0


def detect_columns(
    columns: Sequence[str],
    sample_rows: Sequence[Mapping[str, object]] | None = None,
    minimum_confidence: float = 0.58,
) -> list[MappingSuggestion]:
    """Suggest at most one source column for each canonical field.

    Suggestions are intentionally reviewable. The caller should not apply a
    low-confidence suggestion without showing it to the user.
    """

    rows = list(sample_rows or ())
    candidates: list[MappingSuggestion] = []
    for canonical, aliases in FIELD_ALIASES.items():
        for column in columns:
            best_alias = max(aliases, key=lambda alias: _name_score(column, alias))
            score = _name_score(column, best_alias)
            if score <= 0:
                continue
            reasons = [f"name resembles {best_alias!r}"]
            if rows and canonical in NUMERIC_FIELDS:
                ratio = _numeric_ratio(row.get(column) for row in rows)
                if ratio >= 0.9:
                    score = min(1.0, score + 0.02)
                    reasons.append("sample values are numeric")

                    # Value-range and distribution analysis
                    num_vals = []
                    for r in rows:
                        val = r.get(column)
                        if val is not None:
                            try:
                                num_vals.append(float(str(val).replace(",", "")))
                            except (TypeError, ValueError):
                                pass
                    if num_vals:
                        med = sorted(num_vals)[len(num_vals) // 2]
                        if canonical in {"yield_dry_mass_area", "yield_wet_mass_area"}:
                            # Volumetric yield in bu/ac typically averages 15 - 450 bu/ac (e.g. Yld_Vol_Dr)
                            if 15.0 <= med <= 450.0:
                                score += 0.06
                                reasons.append(f"typical volumetric crop yield range (median ~{med:.1f} bu/ac)")
                            elif med > 500.0:
                                reasons.append(f"mass-per-area rate (median ~{med:.1f} lb/ac or kg/ha)")
                        elif canonical in {"mass_flow_wet", "mass_flow_dry"}:
                            if 0.5 <= med <= 180.0:
                                score += 0.03
                                reasons.append(f"typical harvest mass flow rate (median ~{med:.1f} lb/s)")
                        elif canonical == "speed_m_s":
                            if 0.5 <= med <= 15.0:
                                score += 0.03
                                reasons.append(f"typical harvest speed range (median ~{med:.1f})")
                        elif canonical == "swath_width_m":
                            if 5.0 <= med <= 120.0:
                                score += 0.03
                                reasons.append(f"typical header width range (median ~{med:.1f} ft)")
                        elif canonical == "moisture_pct":
                            if 5.0 <= med <= 45.0:
                                score += 0.03
                                reasons.append(f"typical grain moisture range (median ~{med:.1f}%)")
                elif ratio < 0.5:
                    score *= 0.55
                    reasons.append("many sample values are not numeric")
            if score >= minimum_confidence:
                candidates.append(
                    MappingSuggestion(canonical, str(column), round(score, 3), "; ".join(reasons))
                )

    # Resolve source-column collisions globally so generic names such as "time"
    # do not become two canonical fields at once.
    candidates.sort(key=lambda item: (-item.confidence, item.canonical_field, item.source_column))
    selected_fields: set[str] = set()
    selected_columns: set[str] = set()
    selected: list[MappingSuggestion] = []
    for item in candidates:
        if item.canonical_field in selected_fields or item.source_column in selected_columns:
            continue
        selected.append(item)
        selected_fields.add(item.canonical_field)
        selected_columns.add(item.source_column)
    return sorted(selected, key=lambda item: item.canonical_field)


def suggestions_by_field(suggestions: Sequence[MappingSuggestion]) -> dict[str, MappingSuggestion]:
    return {suggestion.canonical_field: suggestion for suggestion in suggestions}
