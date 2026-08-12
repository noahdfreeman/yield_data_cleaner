# SPDX-License-Identifier: GPL-3.0-or-later
"""Predictable, collision-safe names for guided yield-data runs."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path


def safe_name(value: str | None, fallback: str = "field") -> str:
    """Return a readable filename component without unsafe punctuation."""

    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned or fallback)[:80]


def build_run_stem(
    boundary_name: str | None,
    crop: str | None,
    run_date: date | None = None,
) -> str:
    """Combine field/boundary name, crop, and date into one run identifier."""

    day = run_date or date.today()
    return "_".join(
        (
            safe_name(boundary_name),
            safe_name(crop, "crop").lower(),
            day.isoformat(),
        )
    )


def next_available_run_folder(parent: Path | str, stem: str) -> Path:
    """Choose a new run folder, adding _02, _03, and so on when needed."""

    parent_path = Path(parent)
    candidate = parent_path / stem
    sequence = 2
    while candidate.exists():
        candidate = parent_path / f"{stem}_{sequence:02d}"
        sequence += 1
    return candidate


def run_file_paths(run_folder: Path | str) -> dict[str, Path]:
    """Return all version-0.1 guided-output paths for a selected run folder."""

    folder = Path(run_folder)
    stem = folder.name
    return {
        "mapping": folder / f"{stem}_column_mapping.json",
        "mapping_report": folder / f"{stem}_applied_mapping.json",
        "manifest": folder / f"{stem}_run_manifest.json",
        "boundary_provenance": folder / f"{stem}_boundary_provenance.json",
        "geopackage": folder / f"{stem}_yield_data.gpkg",
    }
