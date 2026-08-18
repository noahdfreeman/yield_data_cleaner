# SPDX-License-Identifier: GPL-3.0-or-later
"""Cleaning recipe contracts, defaults, and serialization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ..version import RECIPE_SCHEMA_VERSION


@dataclass
class CleaningRecipe:
    """Configurable thresholds and enabled stages for yield data cleaning."""

    # Schema & identity
    schema_version: str = RECIPE_SCHEMA_VERSION
    crop_code: str = "corn"
    unit_profile: str = "imperial"

    # Input & position quality
    check_geometry: bool = True
    check_numeric: bool = True
    check_duplicates: bool = True
    check_position_jumps: bool = True
    max_position_jump_m: float = 50.0
    check_timestamp_order: bool = True

    # Header & Motion filters
    filter_header_disengaged: bool = True
    filter_min_speed: bool = True
    min_speed_m_s: float = 0.447  # ~1.0 mph
    filter_max_speed: bool = True
    max_speed_m_s: float = 4.47  # ~10.0 mph
    filter_speed_change: bool = True
    max_speed_change_m_s: float = 1.5

    # Swath width filters
    filter_min_swath: bool = True
    min_swath_width_m: float = 1.0
    filter_swath_change: bool = False
    max_swath_change_m: float = 5.0

    # Pass edge filters
    filter_pass_start: bool = True
    pass_start_count: int = 2
    filter_pass_end: bool = True
    pass_end_count: int = 2

    # Crop yield ranges (canonical SI: kg/ha)
    filter_min_yield: bool = True
    min_yield_kg_ha: float = 627.0  # ~10 bu/ac
    filter_max_yield: bool = True
    max_yield_kg_ha: float = 25000.0  # ~400 bu/ac

    # Moisture ranges (%)
    filter_min_moisture: bool = True
    min_moisture_pct: float = 8.0
    filter_max_moisture: bool = True
    max_moisture_pct: float = 35.0

    # Sensor delays (seconds)
    apply_flow_delay: bool = False
    flow_delay_s: float = 12.0
    apply_moisture_delay: bool = False
    moisture_delay_s: float = 14.0

    # Spatial overlap filter
    filter_overlap: bool = True
    overlap_distance_threshold_m: float = 3.0

    # Robust local spatial outlier filter
    filter_local_outlier: bool = True
    local_outlier_radius_m: float = 25.0
    local_outlier_std_devs: float = 3.0
    local_outlier_min_neighbors: int = 5

    # Custom user overrides
    custom_parameters: dict[str, Any] = field(default_factory=dict)

    # Compatibility properties for alternate parameter names
    @property
    def pass_edge_start_trim_s(self) -> float:
        return float(self.pass_start_count)

    @property
    def pass_edge_end_trim_s(self) -> float:
        return float(self.pass_end_count)

    @property
    def speed_min_m_s(self) -> float:
        return self.min_speed_m_s

    @property
    def speed_max_m_s(self) -> float:
        return self.max_speed_m_s

    @property
    def yield_min_dry_mass_area(self) -> float:
        return self.min_yield_kg_ha

    @property
    def yield_max_dry_mass_area(self) -> float:
        return self.max_yield_kg_ha

    @property
    def spatial_outlier_enabled(self) -> bool:
        return self.filter_local_outlier

    @property
    def spatial_outlier_radius_m(self) -> float:
        return self.local_outlier_radius_m

    @property
    def spatial_outlier_stds(self) -> float:
        return self.local_outlier_std_devs

    @property
    def overlap_filter_enabled(self) -> bool:
        return self.filter_overlap

    def to_dict(self) -> dict[str, Any]:
        """Convert recipe to a serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize recipe to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CleaningRecipe:
        """Create a recipe instance from dictionary data with validation."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in valid_fields:
                kwargs[key] = value
        return cls(**kwargs)

    @classmethod
    def from_json(cls, json_text: str) -> CleaningRecipe:
        """Load a recipe from a JSON string."""
        payload = json.loads(json_text)
        if not isinstance(payload, dict):
            raise ValueError("Recipe JSON root must be an object")
        return cls.from_dict(payload)


def default_recipe_for_crop(
    crop_code: str = "corn", unit_profile: str = "imperial"
) -> CleaningRecipe:
    """Return default recipe tuned for the specified crop."""
    normalized_crop = crop_code.strip().lower()
    if normalized_crop == "soybean":
        return CleaningRecipe(
            crop_code="soybean",
            unit_profile=unit_profile,
            min_yield_kg_ha=336.0,  # ~5 bu/ac
            max_yield_kg_ha=8000.0,  # ~120 bu/ac
            min_moisture_pct=8.0,
            max_moisture_pct=25.0,
        )
    if normalized_crop == "wheat":
        return CleaningRecipe(
            crop_code="wheat",
            unit_profile=unit_profile,
            min_yield_kg_ha=336.0,  # ~5 bu/ac
            max_yield_kg_ha=10000.0,  # ~150 bu/ac
            min_moisture_pct=8.0,
            max_moisture_pct=25.0,
        )
    # Default Corn
    return CleaningRecipe(
        crop_code="corn",
        unit_profile=unit_profile,
        min_yield_kg_ha=627.0,  # ~10 bu/ac
        max_yield_kg_ha=25000.0,  # ~400 bu/ac
        min_moisture_pct=10.0,
        max_moisture_pct=35.0,
    )
