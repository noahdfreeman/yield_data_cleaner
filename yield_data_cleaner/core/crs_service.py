# SPDX-License-Identifier: GPL-3.0-or-later
"""Explainable CRS recognition and analysis-CRS selection contracts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from .column_detection import normalize_name


@dataclass(frozen=True)
class CrsRecognition:
    authid: str | None
    confidence: float
    reason: str
    requires_confirmation: bool
    axis_swap_suspected: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


LONGITUDE_NAMES = {"longitude", "lon", "long", "lng", "xlongitude"}
LATITUDE_NAMES = {"latitude", "lat", "ylatitude"}


def _numbers(values: Iterable[object]) -> list[float]:
    output: list[float] = []
    for value in values:
        if value is None or str(value).strip() == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output.append(number)
    return output


def _within(values: Sequence[float], minimum: float, maximum: float) -> bool:
    return bool(values) and all(minimum <= value <= maximum for value in values)


def recognize_crs(
    x_values: Iterable[object],
    y_values: Iterable[object],
    x_column: str = "x",
    y_column: str = "y",
    declared_authid: str | None = None,
) -> CrsRecognition:
    """Recognize only defensible CRS cases and flag ambiguity for the UI."""

    if declared_authid and str(declared_authid).strip():
        return CrsRecognition(
            str(declared_authid).strip().upper(),
            1.0,
            "CRS was declared by the source layer or format",
            False,
        )

    xs = _numbers(x_values)
    ys = _numbers(y_values)
    if not xs or not ys:
        return CrsRecognition(None, 0.0, "insufficient numeric coordinates", True)

    x_name = normalize_name(x_column)
    y_name = normalize_name(y_column)
    geographic = _within(xs, -180.0, 180.0) and _within(ys, -90.0, 90.0)
    swapped = _within(xs, -90.0, 90.0) and _within(ys, -180.0, 180.0)
    named_lon_lat = x_name in LONGITUDE_NAMES and y_name in LATITUDE_NAMES
    named_lat_lon = x_name in LATITUDE_NAMES and y_name in LONGITUDE_NAMES

    if geographic and named_lon_lat:
        return CrsRecognition("EPSG:4326", 0.97, "longitude/latitude names and ranges", False)
    if swapped and named_lat_lon:
        return CrsRecognition(
            "EPSG:4326",
            0.93,
            "latitude/longitude columns appear reversed",
            True,
            axis_swap_suspected=True,
        )
    if geographic:
        return CrsRecognition(
            "EPSG:4326",
            0.72,
            "coordinate ranges are compatible with longitude/latitude but are not authoritative",
            True,
        )
    return CrsRecognition(
        None,
        0.0,
        "projected coordinates require declared metadata, a vendor profile, or user confirmation",
        True,
    )


def utm_authid(longitude: float, latitude: float) -> str:
    lon = float(longitude)
    lat = float(latitude)
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError("longitude and latitude must be finite")
    if not -180 <= lon <= 180 or not -80 <= lat <= 84:
        raise ValueError("coordinate is outside standard UTM coverage")
    zone = min(60, max(1, int(math.floor((lon + 180.0) / 6.0)) + 1))
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


def choose_analysis_crs(
    source_authid: str, centroid_lon_lat: tuple[float, float] | None = None
) -> str:
    """Choose a projected analysis CRS without conflating it with output CRS."""

    source = str(source_authid).strip().upper()
    if not source:
        raise ValueError("source CRS must be resolved before analysis CRS selection")
    if source not in {"EPSG:4326", "OGC:CRS84"}:
        # QGIS will make the final projected/linear-unit determination. Retaining
        # a declared projected CRS avoids unnecessary datum transformations.
        return source
    if centroid_lon_lat is None:
        raise ValueError("a longitude/latitude centroid is required for geographic source data")
    return utm_authid(*centroid_lon_lat)


def validate_coordinate_extent(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    maximum_field_span_m: float = 100_000.0,
) -> list[str]:
    errors: list[str] = []
    values = tuple(float(value) for value in (xmin, ymin, xmax, ymax))
    if not all(math.isfinite(value) for value in values):
        return ["transformed extent contains non-finite coordinates"]
    if xmax < xmin or ymax < ymin:
        errors.append("transformed extent bounds are reversed")
    if xmax - xmin > maximum_field_span_m or ymax - ymin > maximum_field_span_m:
        errors.append("transformed extent is implausibly large for a single field")
    return errors
