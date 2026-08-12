# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal run-manifest builder for auditable preparation outputs."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..version import CANONICAL_SCHEMA_VERSION, MANIFEST_SCHEMA_VERSION, VERSION


def file_signature(path: str | Path, chunk_size: int = 1_048_576) -> dict[str, Any]:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    stat = source.stat()
    return {
        "path": str(source.resolve()),
        "size_bytes": stat.st_size,
        "sha256": digest.hexdigest(),
    }


def build_manifest(
    source_name: str,
    source_kind: str,
    source_crs: str,
    analysis_crs: str,
    crop_code: str,
    unit_profile: str,
    mapping_profile_source: str,
    processed_records: int,
    input_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "plugin": "Yield Data Cleaner",
        "plugin_version": VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "operation": "canonical_preparation_only",
        "cleaning_applied": False,
        "source": {
            "name": source_name,
            "kind": source_kind,
            "signature": input_signature,
        },
        "source_crs": source_crs,
        "analysis_crs": analysis_crs,
        "crop_code": crop_code,
        "unit_profile": unit_profile,
        "mapping_profile_source": mapping_profile_source,
        "processed_records": int(processed_records),
    }
