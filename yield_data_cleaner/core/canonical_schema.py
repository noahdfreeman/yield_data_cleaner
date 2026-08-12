# SPDX-License-Identifier: GPL-3.0-or-later
"""Vendor-neutral observation fields and validation contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from ..version import CANONICAL_SCHEMA_VERSION


class CleanStatus(str, Enum):
    ACCEPTED = "accepted"
    EXCLUDED = "excluded"
    REVIEW = "review"
    UNAVAILABLE = "unavailable"


class CrsConfidence(str, Enum):
    DECLARED = "declared"
    RECOGNIZED = "recognized"
    USER_CONFIRMED = "user_confirmed"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class CanonicalField:
    name: str
    value_type: str
    unit: str | None = None
    description: str = ""


CANONICAL_FIELDS = (
    CanonicalField("observation_id", "text", description="Stable identifier within a run"),
    CanonicalField("source_index", "integer", description="Original record or feature identifier"),
    CanonicalField("source_name", "text", description="Original file or layer name"),
    CanonicalField("timestamp_utc", "datetime", unit="UTC"),
    CanonicalField("source_sequence", "integer"),
    CanonicalField("crop_code", "text"),
    CanonicalField("unit_profile", "text"),
    CanonicalField("source_crs", "text"),
    CanonicalField("analysis_crs", "text"),
    CanonicalField("crs_confidence", "text"),
    CanonicalField("yield_wet_mass_area", "number", unit="kg/ha"),
    CanonicalField("yield_dry_mass_area", "number", unit="kg/ha"),
    CanonicalField("mass_flow_wet", "number", unit="kg/s"),
    CanonicalField("mass_flow_dry", "number", unit="kg/s"),
    CanonicalField("moisture_pct", "number", unit="percent"),
    CanonicalField("speed_m_s", "number", unit="m/s"),
    CanonicalField("distance_m", "number", unit="m"),
    CanonicalField("duration_s", "number", unit="s"),
    CanonicalField("swath_width_m", "number", unit="m"),
    CanonicalField("heading_deg", "number", unit="degrees"),
    CanonicalField("header_engaged", "boolean"),
    CanonicalField("elevation_m", "number", unit="m"),
    CanonicalField("machine_id", "text"),
    CanonicalField("source_pass_id", "text"),
    CanonicalField("pass_id", "text"),
    CanonicalField("pass_source", "text"),
    CanonicalField("pass_confidence", "number"),
    CanonicalField("clean_status", "text"),
    CanonicalField("filter_flags", "text"),
    CanonicalField("filter_reasons", "text"),
    CanonicalField("manual_action", "text"),
    CanonicalField("boundary_status", "text"),
)

CANONICAL_FIELD_NAMES = tuple(item.name for item in CANONICAL_FIELDS)


@dataclass
class CanonicalObservation:
    observation_id: str
    source_index: int
    source_name: str
    timestamp_utc: str | None = None
    source_sequence: int | None = None
    crop_code: str | None = None
    unit_profile: str | None = None
    source_crs: str | None = None
    analysis_crs: str | None = None
    crs_confidence: CrsConfidence = CrsConfidence.UNRESOLVED
    measurements: dict[str, Any] = field(default_factory=dict)
    source_attributes: dict[str, Any] = field(default_factory=dict)
    clean_status: CleanStatus = CleanStatus.UNAVAILABLE
    filter_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = CANONICAL_SCHEMA_VERSION
        payload["crs_confidence"] = self.crs_confidence.value
        payload["clean_status"] = self.clean_status.value
        return payload


def validate_observation(observation: CanonicalObservation) -> list[str]:
    """Return validation errors without mutating the observation."""

    errors: list[str] = []
    if not str(observation.observation_id).strip():
        errors.append("observation_id is required")
    if observation.source_index < 0:
        errors.append("source_index must be zero or greater")
    if not str(observation.source_name).strip():
        errors.append("source_name is required")
    if observation.timestamp_utc is None and observation.source_sequence is None:
        errors.append("timestamp_utc or source_sequence is required")
    if observation.crop_code not in (None, "corn", "soybean", "wheat"):
        errors.append(f"unsupported crop_code: {observation.crop_code}")
    return errors


def source_attribute_collisions(attributes: Mapping[str, Any]) -> tuple[str, ...]:
    """Return source fields that collide with canonical names."""

    canonical = set(CANONICAL_FIELD_NAMES)
    return tuple(sorted(str(name) for name in attributes if str(name) in canonical))
