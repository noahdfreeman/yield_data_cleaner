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
    "x": ("longitude", "lon", "long", "x", "xcoord", "xcoordinate", "easting", "east"),
    "y": ("latitude", "lat", "y", "ycoord", "ycoordinate", "northing", "north"),
    "timestamp_utc": ("timestamp", "datetime", "dateandtime", "gpsdatetime", "gpstime", "utc"),
    "date": ("date", "harvestdate", "gpsdate"),
    "time": ("time", "harvesttime", "localtime"),
    "source_sequence": ("sequence", "seq", "record", "recordid", "pointid", "index"),
    "source_pass_id": ("pass", "passid", "track", "trackid", "swathid", "loadid"),
    "yield_dry_mass_area": (
        "yield",
        "dryyield",
        "yielddry",
        "yieldbuac",
        "dryyieldbuac",
        "yieldmassdry",
        "yieldvolume",
    ),
    "yield_wet_mass_area": ("wetyield", "yieldwet", "wetmassyield", "wetyieldmass"),
    "mass_flow_wet": ("massflow", "wetmassflow", "flow", "flowrate", "grainflow", "grainflowwet"),
    "mass_flow_dry": ("drymassflow", "grainflowdry"),
    "moisture_pct": ("moisture", "moisturepct", "grainmoisture", "cropmoisture", "mst"),
    "speed_m_s": ("speed", "groundspeed", "velocity", "gpsspeed", "speedmph", "speedkph"),
    "distance_m": ("distance", "traveldistance", "dist", "distanceft", "distancem"),
    "duration_s": ("duration", "seconds", "interval", "elapsedtime", "timesec"),
    "swath_width_m": ("swath", "swathwidth", "headerwidth", "width", "cutwidth", "effectivewidth"),
    "heading_deg": ("heading", "bearing", "trackangle", "direction", "course"),
    "header_engaged": (
        "headerstatus",
        "header",
        "headerdown",
        "engaged",
        "implementstatus",
        "recording",
    ),
    "elevation_m": ("elevation", "altitude", "height", "gpsaltitude", "elev"),
    "crop_code": ("crop", "croptype", "commodity", "product", "harvestedcrop"),
    "machine_id": ("machine", "machineid", "device", "deviceid", "combine", "serialnumber"),
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
    if target in normalized and len(target) >= 4:
        return 0.83
    if normalized in target and len(normalized) >= 4:
        return 0.76
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
