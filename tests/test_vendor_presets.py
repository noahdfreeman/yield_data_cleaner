# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for built-in vendor presets and signature matching."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.vendor_presets import get_vendor_preset, match_vendor_preset


class VendorPresetTests(unittest.TestCase):
    def test_get_agleader_preset(self) -> None:
        profile = get_vendor_preset("agleader", crop_code="corn")
        self.assertEqual(profile.profile_name, "Ag Leader Text")
        self.assertEqual(profile.mapping.get("x"), "Longitude")
        self.assertEqual(profile.mapping.get("y"), "Latitude")
        self.assertEqual(profile.mapping.get("yield_wet_mass_area"), "Yield (bu/ac)")
        self.assertEqual(profile.source_units.get("yield_wet_mass_area"), "bu/ac")

    def test_get_greenstar_preset(self) -> None:
        profile = get_vendor_preset("greenstar", crop_code="soybean")
        self.assertEqual(profile.profile_name, "John Deere / GreenStar Text")
        self.assertEqual(profile.mapping.get("x"), "LONGITUDE")
        self.assertEqual(profile.mapping.get("y"), "LATITUDE")
        self.assertEqual(profile.mapping.get("yield_wet_mass_area"), "DRY_YIELD")

    def test_match_vendor_preset_signatures(self) -> None:
        ag_headers = [
            "Longitude",
            "Latitude",
            "Time",
            "Yield (bu/ac)",
            "Moisture (%)",
            "Speed (mph)",
        ]
        self.assertEqual(match_vendor_preset(ag_headers), "agleader")

        jd_headers = ["LONGITUDE", "LATITUDE", "DRY_YIELD", "MOISTURE", "SWATH_WIDTH", "PASS_NUM"]
        self.assertEqual(match_vendor_preset(jd_headers), "greenstar")

        unknown_headers = ["ColA", "ColB", "ColC"]
        self.assertIsNone(match_vendor_preset(unknown_headers))


if __name__ == "__main__":
    unittest.main()
