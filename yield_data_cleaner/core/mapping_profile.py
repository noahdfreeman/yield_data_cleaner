# SPDX-License-Identifier: GPL-3.0-or-later
"""Serializable, vendor-neutral column mapping profiles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .canonical_schema import CANONICAL_FIELD_NAMES
from .crop_profiles import CROP_PROFILES

MAPPING_PROFILE_VERSION = "1.0"
MAX_PROFILE_BYTES = 1_048_576
UNIT_PROFILES = {"imperial", "metric"}


@dataclass
class MappingProfile:
    mapping: dict[str, str]
    crop_code: str
    unit_profile: str = "imperial"
    source_crs: str | None = None
    source_units: dict[str, str] = field(default_factory=dict)
    profile_name: str = "User mapping"
    profile_version: str = MAPPING_PROFILE_VERSION

    def validate(self, available_columns: list[str] | tuple[str, ...] | None = None) -> list[str]:
        errors: list[str] = []
        if self.profile_version != MAPPING_PROFILE_VERSION:
            errors.append(f"unsupported mapping profile version: {self.profile_version}")
        if self.crop_code not in CROP_PROFILES:
            errors.append(f"unsupported crop_code: {self.crop_code}")
        if self.unit_profile not in UNIT_PROFILES:
            errors.append(f"unsupported unit_profile: {self.unit_profile}")
        allowed = set(CANONICAL_FIELD_NAMES) | {"x", "y", "date", "time"}
        unknown = sorted(set(self.mapping) - allowed)
        if unknown:
            errors.append(f"unknown canonical mapping fields: {', '.join(unknown)}")
        empty = sorted(key for key, value in self.mapping.items() if not str(value).strip())
        if empty:
            errors.append(f"empty source-column mappings: {', '.join(empty)}")
        source_columns = [str(value) for value in self.mapping.values() if str(value).strip()]
        if len(source_columns) != len(set(source_columns)):
            errors.append("one source column cannot map to multiple canonical fields")
        if available_columns is not None:
            available = set(available_columns)
            missing = sorted(column for column in source_columns if column not in available)
            if missing:
                errors.append(f"mapped source columns are missing: {', '.join(missing)}")
        unknown_units = sorted(set(self.source_units) - set(self.mapping))
        if unknown_units:
            errors.append(f"unit overrides have no mapping: {', '.join(unknown_units)}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MappingProfile":
        if not isinstance(payload, Mapping):
            raise ValueError("mapping profile root must be an object")
        mapping = payload.get("mapping", {})
        source_units = payload.get("source_units", {})
        if not isinstance(mapping, Mapping) or not isinstance(source_units, Mapping):
            raise ValueError("mapping and source_units must be objects")
        profile = cls(
            mapping={str(key): str(value) for key, value in mapping.items()},
            crop_code=str(payload.get("crop_code", "")),
            unit_profile=str(payload.get("unit_profile", "imperial")).lower(),
            source_crs=(str(payload["source_crs"]).strip() if payload.get("source_crs") else None),
            source_units={str(key): str(value) for key, value in source_units.items()},
            profile_name=str(payload.get("profile_name", "User mapping")),
            profile_version=str(payload.get("profile_version", MAPPING_PROFILE_VERSION)),
        )
        errors = profile.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return profile


def save_mapping_profile(profile: MappingProfile, path: str | Path) -> Path:
    errors = profile.validate()
    if errors:
        raise ValueError("; ".join(errors))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    return destination


def load_mapping_profile(path: str | Path) -> MappingProfile:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"mapping profile does not exist: {source}")
    if source.stat().st_size > MAX_PROFILE_BYTES:
        raise ValueError("mapping profile exceeds the 1 MiB safety limit")
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"mapping profile is not valid UTF-8 JSON: {exc}") from exc
    return MappingProfile.from_dict(payload)
