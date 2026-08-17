# SPDX-License-Identifier: GPL-3.0-or-later
"""QGIS geometry operations for a reviewed operational harvest extent."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable

from qgis.core import QgsGeometry, QgsPointXY


@dataclass(frozen=True)
class BoundaryDerivationResult:
    geometry: QgsGeometry
    method: str
    confidence: float
    assumptions: tuple[str, ...]
    point_count: int
    width_value_count: int

    def provenance(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("geometry")
        return payload


def _valid_width(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def derive_operational_boundary(
    points: Iterable[QgsPointXY],
    swath_widths_m: Iterable[object] | None = None,
    default_swath_width_m: float | None = None,
    gap_closing_m: float = 1.0,
    concavity: float = 0.3,
) -> BoundaryDerivationResult:
    point_list = [QgsPointXY(point) for point in points]
    if len(point_list) < 3:
        raise ValueError("at least three valid point observations are required")
    if not 0 <= concavity <= 1:
        raise ValueError("concavity must be between 0 and 1")
    if gap_closing_m < 0 or not math.isfinite(gap_closing_m):
        raise ValueError("gap closing distance must be finite and zero or greater")

    provided = list(swath_widths_m or ())
    widths = [_valid_width(value) for value in provided]
    default_width = _valid_width(default_swath_width_m)
    usable_count = sum(width is not None for width in widths)

    if usable_count or default_width is not None:
        footprints = []
        for index, point in enumerate(point_list):
            width = widths[index] if index < len(widths) else None
            width = width or default_width
            if width is None:
                continue
            footprints.append(QgsGeometry.fromPointXY(point).buffer(width / 2.0, 8))
        if len(footprints) >= 3:
            geometry = QgsGeometry.unaryUnion(footprints)
            if gap_closing_m:
                geometry = geometry.buffer(gap_closing_m, 8).buffer(-gap_closing_m, 8)
            confidence = 0.88 if usable_count == len(point_list) else 0.72
            assumptions = (
                "Circular point footprints approximate harvest coverage before pass reconstruction",
                "Boundary must be visually reviewed and is not a legal property boundary",
            )
            if default_width is not None and usable_count < len(point_list):
                assumptions += (f"Missing widths used default {default_width:.3f} m",)
            return BoundaryDerivationResult(
                geometry,
                "point_footprint_union",
                confidence,
                assumptions,
                len(point_list),
                usable_count,
            )

    geometry = QgsGeometry.fromMultiPointXY(point_list).concaveHull(concavity, False)
    return BoundaryDerivationResult(
        geometry,
        "concave_hull_fallback",
        0.55,
        (
            f"Concave hull target percent {concavity:.3f}",
            "No reliable swath widths were available",
            "Boundary must be visually reviewed and is not a legal property boundary",
        ),
        len(point_list),
        usable_count,
    )


def validate_boundary_geometry(
    geometry: QgsGeometry,
    minimum_area_m2: float = 100.0,
) -> tuple[QgsGeometry, bool]:
    if geometry is None or geometry.isNull() or geometry.isEmpty():
        raise ValueError("boundary geometry is empty")
    repaired = False
    candidate = QgsGeometry(geometry)
    if not candidate.isGeosValid():
        candidate = candidate.makeValid()
        repaired = True
    if candidate.isNull() or candidate.isEmpty() or not candidate.isGeosValid():
        raise ValueError("boundary geometry could not be repaired safely")
    if candidate.area() < minimum_area_m2:
        raise ValueError(f"boundary area is smaller than {minimum_area_m2:g} square meters")
    return candidate, repaired


def fill_polygon_holes(geometry: QgsGeometry, max_hole_area: float = 0.0) -> QgsGeometry:
    """Remove interior rings (holes) from polygon / multipolygon geometry.
    
    If max_hole_area <= 0, all interior holes are removed.
    """
    if geometry is None or geometry.isNull() or geometry.isEmpty():
        return geometry

    # Approach 1: Reconstruct directly from exterior boundary rings
    try:
        if geometry.isMultipart():
            multi_poly = geometry.asMultiPolygon()
            if multi_poly:
                exterior_only = []
                for part in multi_poly:
                    if part and len(part) > 0:
                        exterior_only.append([part[0]])
                if exterior_only:
                    res = QgsGeometry.fromMultiPolygonXY(exterior_only)
                    if res and not res.isEmpty() and res.isGeosValid():
                        return res
        else:
            poly = geometry.asPolygon()
            if poly and len(poly) > 0:
                res = QgsGeometry.fromPolygonXY([poly[0]])
                if res and not res.isEmpty() and res.isGeosValid():
                    return res
    except Exception:
        pass

    # Approach 2: removeInteriorRings on copy
    try:
        candidate = QgsGeometry(geometry)
        if hasattr(candidate, "removeInteriorRings"):
            candidate.removeInteriorRings(-1.0)
            if not candidate.isEmpty() and candidate.isGeosValid():
                return candidate
    except Exception:
        pass

    return geometry


def simplify_boundary_geometry(geometry: QgsGeometry, tolerance: float = 1.0) -> QgsGeometry:
    """Simplify polygon geometry to smooth contours and reduce vertex density."""
    if geometry is None or geometry.isNull() or geometry.isEmpty():
        return geometry
    try:
        simplified = geometry.simplify(tolerance)
        if simplified and not simplified.isEmpty() and simplified.isGeosValid():
            return simplified
    except Exception:
        pass
    return geometry
