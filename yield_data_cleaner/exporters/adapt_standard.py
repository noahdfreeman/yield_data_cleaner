# SPDX-License-Identifier: GPL-3.0-or-later
"""Export cleaned yield observations and coverage to AgGateway ADAPT Standard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..boundaries.coverage_builder import build_pass_coverage_footprints
from ..core.filter_engine import CleaningRunResult
from ..version import VERSION

ADAPT_STANDARD_VERSION = "2.1.0"


@dataclass
class AdaptExportSummary:
    """Summary of the exported ADAPT Standard package."""

    package_directory: str
    manifest_path: str
    context_path: str
    logged_data_path: str
    coverage_path: str
    accepted_features_count: int

    @property
    def package_dir(self) -> str:
        return self.package_directory


def export_adapt_standard_package(
    target_dir: Path | str | None = None,
    field_name: str = "Field",
    crop_code: str = "corn",
    observations: Sequence[Mapping[str, Any]] = (),
    cleaning_result: CleaningRunResult | None = None,
    grower_name: str = "Default Grower",
    farm_name: str = "Default Farm",
    analysis_crs: str = "EPSG:4326",
    output_dir: Path | str | None = None,
    **kwargs: Any,
) -> AdaptExportSummary:
    """Export cleaned harvest observations as an AgGateway ADAPT Standard package."""
    destination = Path(output_dir or target_dir or kwargs.get("output_dr") or Path.cwd())
    destination.mkdir(parents=True, exist_ok=True)

    manifest_path = destination / "adapt_manifest.json"
    context_path = destination / "context.json"
    logged_data_path = destination / "logged_data.json"
    coverage_path = destination / "spatial_coverage.geojson"

    # Filter accepted observations
    accepted_obs: list[Mapping[str, Any]] = []
    for idx, obs in enumerate(observations):
        if cleaning_result and idx < len(cleaning_result.observation_updates):
            update = cleaning_result.observation_updates[idx]
            if update.get("clean_status") == "accepted":
                accepted_obs.append(obs)
        elif obs.get("clean_status") in ("accepted", None, ""):
            accepted_obs.append(obs)

    # 1. Generate Coverage Footprints GeoJSON
    footprints = build_pass_coverage_footprints(accepted_obs)
    geojson_payload = {
        "type": "FeatureCollection",
        "name": f"{field_name}_harvest_coverage",
        "crs": {
            "type": "name",
            "properties": {"name": analysis_crs},
        },
        "features": [fp.to_geojson_feature() for fp in footprints],
    }
    coverage_path.write_text(json.dumps(geojson_payload, indent=2), encoding="utf-8")

    # 2. Compute aggregate metrics
    yields = [
        float(y) for obs in accepted_obs
        if (y := obs.get("yield_wet_mass_area")) is not None
    ]
    moistures = [
        float(m) for obs in accepted_obs
        if (m := obs.get("moisture_pct")) is not None
    ]

    mean_yield = (sum(yields) / len(yields)) if yields else 0.0
    mean_moisture = (sum(moistures) / len(moistures)) if moistures else 0.0
    total_area_m2 = sum(fp.area_m2 for fp in footprints)
    total_area_ha = total_area_m2 / 10000.0
    total_mass_kg = total_area_ha * mean_yield

    # 3. Context JSON
    context_data = {
        "adapt_version": ADAPT_STANDARD_VERSION,
        "grower": {"name": grower_name},
        "farm": {"name": farm_name},
        "field": {"name": field_name},
        "crop": {"code": crop_code},
        "operation": "Harvest",
        "generator": {
            "name": "Yield Data Cleaner for QGIS",
            "version": VERSION,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    context_path.write_text(json.dumps(context_data, indent=2), encoding="utf-8")

    # 4. Logged Data Summary JSON
    logged_data = {
        "operation": "Harvest",
        "crop_code": crop_code,
        "total_harvest_mass_kg": round(total_mass_kg, 2),
        "total_harvest_area_ha": round(total_area_ha, 4),
        "mean_yield_kg_ha": round(mean_yield, 2),
        "mean_moisture_pct": round(mean_moisture, 2),
        "total_observations": len(observations),
        "accepted_observations": len(accepted_obs),
        "excluded_observations": len(observations) - len(accepted_obs),
    }
    logged_data_path.write_text(json.dumps(logged_data, indent=2), encoding="utf-8")

    # 5. Manifest JSON
    manifest_data = {
        "adapt_standard_version": ADAPT_STANDARD_VERSION,
        "files": {
            "context": context_path.name,
            "logged_data": logged_data_path.name,
            "spatial_coverage": coverage_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return AdaptExportSummary(
        package_directory=str(target_dir),
        manifest_path=str(manifest_path),
        context_path=str(context_path),
        logged_data_path=str(logged_data_path),
        coverage_path=str(coverage_path),
        accepted_features_count=len(accepted_obs),
    )
