# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable product settings shared by UI, algorithms, and outputs."""

from ..version import VERSION

PLUGIN_NAME = "Yield Data Cleaner"
PLUGIN_ID = "yield_data_cleaner"
PLUGIN_VERSION = VERSION
PROVIDER_ID = PLUGIN_ID
PROVIDER_NAME = PLUGIN_NAME
DEFAULT_UNIT_SYSTEM = "Imperial"
SUPPORTED_UNIT_SYSTEMS = ("Imperial", "Metric")
SUPPORTED_CROPS = ("corn", "soybean", "wheat")
