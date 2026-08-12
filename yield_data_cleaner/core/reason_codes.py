# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable, public reason codes used by versioned cleaning recipes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReasonCode:
    code: str
    category: str
    description: str


REASON_CODES = (
    ReasonCode("invalid_geometry", "input", "Geometry is missing, empty, or invalid"),
    ReasonCode("invalid_numeric", "input", "A required numeric value is not finite"),
    ReasonCode("duplicate_observation", "input", "Observation duplicates another record"),
    ReasonCode("position_jump", "position", "Coordinate jump is implausible for the sequence"),
    ReasonCode("invalid_timestamp", "time", "Timestamp is missing, invalid, or reversed"),
    ReasonCode("outside_boundary", "boundary", "Observation is outside the accepted boundary"),
    ReasonCode("header_disengaged", "motion", "Header or implement is disengaged"),
    ReasonCode("speed_below_min", "motion", "Ground speed is below the accepted minimum"),
    ReasonCode("speed_above_max", "motion", "Ground speed is above the accepted maximum"),
    ReasonCode("speed_change", "motion", "Ground-speed change exceeds the accepted threshold"),
    ReasonCode("swath_below_min", "swath", "Swath width is below the accepted minimum"),
    ReasonCode("swath_change", "swath", "Swath-width change exceeds the accepted threshold"),
    ReasonCode("pass_start", "pass", "Observation is within the excluded pass-start interval"),
    ReasonCode("pass_end", "pass", "Observation is within the excluded pass-end interval"),
    ReasonCode("yield_below_min", "yield", "Yield is below the accepted minimum"),
    ReasonCode("yield_above_max", "yield", "Yield is above the accepted maximum"),
    ReasonCode("moisture_below_min", "moisture", "Moisture is below the accepted minimum"),
    ReasonCode("moisture_above_max", "moisture", "Moisture is above the accepted maximum"),
    ReasonCode("harvest_overlap", "spatial", "Observation overlaps previously accepted coverage"),
    ReasonCode("local_yield_outlier", "spatial", "Yield is a robust local spatial outlier"),
    ReasonCode("low_pass_confidence", "pass", "Pass assignment requires review"),
    ReasonCode("manual_exclude", "manual", "User explicitly excluded the observation"),
    ReasonCode("manual_restore", "manual", "User explicitly restored the observation"),
)

REASON_CODE_REGISTRY = {item.code: item for item in REASON_CODES}

if len(REASON_CODE_REGISTRY) != len(REASON_CODES):
    raise RuntimeError("reason-code registry contains duplicate codes")
