# SPDX-License-Identifier: GPL-3.0-or-later
"""Import AgGateway ADAPT Standard harvest packages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AdaptImportResult:
    """Parsed harvest data and context from an ADAPT Standard package."""

    crop_code: str
    field_name: str
    grower_name: str = ""
    farm_name: str = ""
    total_area_ha: float = 0.0
    mean_yield_kg_ha: float = 0.0
    observations: list[dict[str, Any]] = field(default_factory=list)


def import_adapt_standard_package(package_dir_or_manifest: Path) -> AdaptImportResult:
    """Read and validate an ADAPT Standard package into canonical harvest structures."""
    pkg_dir = package_dir_or_manifest.parent if package_dir_or_manifest.is_file() else package_dir_or_manifest
    if not pkg_dir.exists() or not pkg_dir.is_dir():
        raise FileNotFoundError(f"ADAPT package directory not found: {pkg_dir}")

    context_file = pkg_dir / "context.json"
    logged_data_file = pkg_dir / "logged_data.json"
    coverage_file = pkg_dir / "spatial_coverage.geojson"

    if not context_file.exists():
        raise ValueError(f"Missing required context.json in ADAPT package: {pkg_dir}")

    context = json.loads(context_file.read_text(encoding="utf-8"))
    crop_code = context.get("crop", {}).get("code", "corn")
    field_name = context.get("field", {}).get("name", "Field")
    grower_name = context.get("grower", {}).get("name", "")
    farm_name = context.get("farm", {}).get("name", "")

    logged_data = {}
    if logged_data_file.exists():
        logged_data = json.loads(logged_data_file.read_text(encoding="utf-8"))

    observations: list[dict[str, Any]] = []
    if coverage_file.exists():
        geojson = json.loads(coverage_file.read_text(encoding="utf-8"))
        features = geojson.get("features", [])
        for idx, feat in enumerate(features):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [[]])
            # Centroid approximation of polygon footprint
            if coords and len(coords[0]) >= 4:
                pts = coords[0]
                cx = sum(p[0] for p in pts[:4]) / 4.0
                cy = sum(p[1] for p in pts[:4]) / 4.0
            else:
                cx, cy = 0.0, 0.0

            observations.append({
                "source_index": idx,
                "observation_id": props.get("observation_id", f"adapt_{idx}"),
                "pass_id": str(props.get("pass_id", "1")),
                "x": cx,
                "y": cy,
                "yield_wet_mass_area": props.get("yield_wet_mass_area"),
                "swath_width_m": props.get("swath_width_m"),
            })

    return AdaptImportResult(
        crop_code=crop_code,
        field_name=field_name,
        grower_name=grower_name,
        farm_name=farm_name,
        total_area_ha=float(logged_data.get("total_harvest_area_ha", 0.0)),
        mean_yield_kg_ha=float(logged_data.get("mean_yield_kg_ha", 0.0)),
        observations=observations,
    )
