# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit, dependency-free yield and spatial unit conversions."""

from __future__ import annotations

import math

ACRE_TO_HECTARE = 0.40468564224
FOOT_TO_METER = 0.3048
INCH_TO_METER = 0.0254
MILE_TO_METER = 1609.344
POUND_TO_KILOGRAM = 0.45359237


def _finite(value: float, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def acres_to_hectares(value: float) -> float:
    return _finite(value, "acres") * ACRE_TO_HECTARE


def hectares_to_acres(value: float) -> float:
    return _finite(value, "hectares") / ACRE_TO_HECTARE


def feet_to_meters(value: float) -> float:
    return _finite(value, "feet") * FOOT_TO_METER


def meters_to_feet(value: float) -> float:
    return _finite(value, "meters") / FOOT_TO_METER


def inches_to_meters(value: float) -> float:
    return _finite(value, "inches") * INCH_TO_METER


def mph_to_m_s(value: float) -> float:
    return _finite(value, "mph") * MILE_TO_METER / 3600.0


def m_s_to_mph(value: float) -> float:
    return _finite(value, "m/s") * 3600.0 / MILE_TO_METER


def bushels_per_acre_to_kg_per_hectare(value: float, test_weight_lb_per_bushel: float) -> float:
    bushels = _finite(value, "bushels per acre")
    test_weight = _finite(test_weight_lb_per_bushel, "test weight")
    if test_weight <= 0:
        raise ValueError("test weight must be greater than zero")
    return bushels * test_weight * POUND_TO_KILOGRAM / ACRE_TO_HECTARE


def kg_per_hectare_to_bushels_per_acre(value: float, test_weight_lb_per_bushel: float) -> float:
    kilograms = _finite(value, "kg per hectare")
    test_weight = _finite(test_weight_lb_per_bushel, "test weight")
    if test_weight <= 0:
        raise ValueError("test weight must be greater than zero")
    return kilograms * ACRE_TO_HECTARE / (test_weight * POUND_TO_KILOGRAM)


def adjust_yield_for_moisture(
    value: float, source_moisture_pct: float, target_moisture_pct: float
) -> float:
    """Adjust a wet-mass yield between moisture bases by conserved dry matter."""

    yield_value = _finite(value, "yield")
    source = _finite(source_moisture_pct, "source moisture")
    target = _finite(target_moisture_pct, "target moisture")
    if not 0 <= source < 100 or not 0 <= target < 100:
        raise ValueError("moisture percentages must be between 0 and less than 100")
    return yield_value * (100.0 - source) / (100.0 - target)
