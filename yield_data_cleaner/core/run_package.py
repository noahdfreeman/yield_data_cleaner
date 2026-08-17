# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete run package and export generators."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..review.builder import generate_html_review
from ..version import VERSION, MANIFEST_SCHEMA_VERSION
from .filter_engine import CleaningRunResult
from .mapping_profile import MappingProfile
from .reason_codes import REASON_CODE_REGISTRY
from .recipe import CleaningRecipe


@dataclass
class RunPackageSummary:
    """Paths and summary of the generated run package."""

    run_directory: str
    manifest_path: str
    recipe_path: str
    mapping_path: str
    summary_csv_path: str
    review_html_path: str
    run_log_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "run_directory": self.run_directory,
            "manifest_path": self.manifest_path,
            "recipe_path": self.recipe_path,
            "mapping_path": self.mapping_path,
            "summary_csv_path": self.summary_csv_path,
            "review_html_path": self.review_html_path,
            "run_log_path": self.run_log_path,
        }


def write_filter_summary_csv(
    target_path: Path,
    cleaning_result: CleaningRunResult,
    total_observations: int,
) -> None:
    """Write tabular filter-by-filter breakdown CSV."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["reason_code", "category", "description", "excluded_count", "impact_pct"])
        for code, count in sorted(cleaning_result.reason_counts.items(), key=lambda i: i[1], reverse=True):
            reg = REASON_CODE_REGISTRY.get(code)
            desc = reg.description if reg else code
            cat = reg.category if reg else "general"
            pct = round((count / total_observations * 100.0), 2) if total_observations else 0.0
            writer.writerow([code, cat, desc, count, pct])


def export_cleaned_csv(
    target_path: Path,
    observations: Sequence[Mapping[str, Any]],
    cleaning_result: CleaningRunResult,
) -> int:
    """Export accepted observations to CSV with original and normalized canonical fields."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    accepted_count = 0

    if not observations:
        return 0

    # Determine field list
    sample_obs = observations[0]
    fieldnames = list(sample_obs.keys())
    for extra in ("clean_status", "filter_reasons"):
        if extra not in fieldnames:
            fieldnames.append(extra)

    with target_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, obs in enumerate(observations):
            update = cleaning_result.observation_updates[idx] if idx < len(cleaning_result.observation_updates) else {}
            if update.get("clean_status") == "accepted":
                row = dict(obs)
                row["clean_status"] = "accepted"
                row["filter_reasons"] = update.get("filter_reasons", "")
                writer.writerow(row)
                accepted_count += 1

    return accepted_count


def write_run_package(
    output_dir: Path,
    run_name: str,
    field_name: str,
    crop_code: str,
    unit_profile: str,
    observations: Sequence[Mapping[str, Any]],
    cleaning_result: CleaningRunResult,
    mapping_profile: MappingProfile | None = None,
    recipe: CleaningRecipe | None = None,
    analysis_crs: str = "Unknown",
    source_crs: str = "Unknown",
    grid_size_ft: float = 30.0,
    boundary_coords: Sequence[Sequence[tuple[float, float]]] | None = None,
) -> RunPackageSummary:
    """Write complete auditable run package files into the target folder."""
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / f"{run_name}_run_manifest.json"
    recipe_path = output_dir / f"{run_name}_cleaning_recipe.json"
    mapping_path = output_dir / f"{run_name}_column_mapping.json"
    summary_csv_path = output_dir / f"{run_name}_filter_summary.csv"
    review_html_path = output_dir / f"{run_name}_yield_cleaning_review.html"
    run_log_path = output_dir / f"{run_name}_run_log.txt"

    # 1. Recipe JSON
    effective_recipe = recipe or cleaning_result.recipe
    recipe_path.write_text(effective_recipe.to_json(), encoding="utf-8")

    # 2. Mapping JSON
    if mapping_profile:
        mapping_path.write_text(mapping_profile.to_json(), encoding="utf-8")
    else:
        mapping_path.write_text(json.dumps({"crop_code": crop_code, "unit_profile": unit_profile}, indent=2), encoding="utf-8")

    # 3. Filter Summary CSV
    write_filter_summary_csv(summary_csv_path, cleaning_result, len(observations))

    # 4. Manifest JSON
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "plugin_version": VERSION,
        "run_name": run_name,
        "field_name": field_name,
        "crop_code": crop_code,
        "unit_profile": unit_profile,
        "source_crs": source_crs,
        "analysis_crs": analysis_crs,
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cleaning_summary": cleaning_result.to_dict(),
        "files": {
            "recipe": recipe_path.name,
            "mapping": mapping_path.name,
            "filter_summary_csv": summary_csv_path.name,
            "review_html": review_html_path.name,
            "run_log": run_log_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    # 5. Run Log TXT
    log_lines = [
        "================================================================================",
        "YIELD DATA CLEANER - RUN LOG",
        "================================================================================",
        f"Run Name:            {run_name}",
        f"Field Name:          {field_name}",
        f"Crop:                {crop_code}",
        f"Units:               {unit_profile}",
        f"Plugin Version:      {VERSION}",
        f"Execution Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Source CRS:          {source_crs}",
        f"Analysis CRS:        {analysis_crs}",
        f"Grid Size (ft):      {grid_size_ft}",
        "--------------------------------------------------------------------------------",
        "CLEANING SUMMARY & STATS",
        "--------------------------------------------------------------------------------",
        f"Total Observations:    {cleaning_result.total_observations:,}",
        f"Accepted Observations: {cleaning_result.accepted_count:,} ({(cleaning_result.accepted_count / cleaning_result.total_observations * 100.0 if cleaning_result.total_observations else 0.0):.1f}%)",
        f"Excluded Observations: {cleaning_result.excluded_count:,} ({(cleaning_result.excluded_count / cleaning_result.total_observations * 100.0 if cleaning_result.total_observations else 0.0):.1f}%)",
        "",
        "FILTER EXCLUSION BREAKDOWN:",
    ]
    for reason, count in sorted(cleaning_result.reason_counts.items(), key=lambda x: x[1], reverse=True):
        reg = REASON_CODE_REGISTRY.get(reason)
        desc = reg.description if reg else reason
        pct = (count / cleaning_result.total_observations * 100.0) if cleaning_result.total_observations else 0.0
        log_lines.append(f"  - {reason:<22} : {count:>7,} points ({pct:5.1f}%) | {desc}")

    log_lines.extend([
        "",
        "--------------------------------------------------------------------------------",
        "APPLIED RECIPE THRESHOLDS",
        "--------------------------------------------------------------------------------",
        json.dumps(effective_recipe.to_dict(), indent=2),
        "",
        "--------------------------------------------------------------------------------",
        "STATUS: Completed successfully (non-destructive; raw records preserved).",
        "================================================================================",
    ])
    run_log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    # 6. Standalone Review HTML
    html_content = generate_html_review(
        run_name=run_name,
        field_name=field_name,
        crop_code=crop_code,
        unit_profile=unit_profile,
        observations=observations,
        cleaning_result=cleaning_result,
        analysis_crs=analysis_crs,
        grid_size_ft=grid_size_ft,
        boundary_coords=boundary_coords,
    )
    review_html_path.write_text(html_content, encoding="utf-8")

    # 7. Companion data folder
    data_dir = output_dir / f"{run_name}_yield_cleaning_review_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "summary.json").write_text(json.dumps(cleaning_result.to_dict(), indent=2, default=str), encoding="utf-8")

    return RunPackageSummary(
        run_directory=str(output_dir),
        manifest_path=str(manifest_path),
        recipe_path=str(recipe_path),
        mapping_path=str(mapping_path),
        summary_csv_path=str(summary_csv_path),
        review_html_path=str(review_html_path),
        run_log_path=str(run_log_path),
    )
