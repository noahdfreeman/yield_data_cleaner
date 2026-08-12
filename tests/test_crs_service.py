# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.crs_service import (
    choose_analysis_crs,
    recognize_crs,
    utm_authid,
    validate_coordinate_extent,
)


class CrsServiceTests(unittest.TestCase):
    def test_declared_crs_is_authoritative(self):
        result = recognize_crs([], [], declared_authid="epsg:26916")
        self.assertEqual(result.authid, "EPSG:26916")
        self.assertFalse(result.requires_confirmation)

    def test_named_lon_lat_recognized(self):
        result = recognize_crs([-86.1, -86.2], [40.1, 40.2], "Longitude", "Latitude")
        self.assertEqual(result.authid, "EPSG:4326")
        self.assertFalse(result.requires_confirmation)

    def test_generic_geographic_coordinates_require_confirmation(self):
        result = recognize_crs([-86.1], [40.1], "X", "Y")
        self.assertEqual(result.authid, "EPSG:4326")
        self.assertTrue(result.requires_confirmation)

    def test_axis_swap_is_flagged(self):
        result = recognize_crs([40.1], [-86.1], "Latitude", "Longitude")
        self.assertTrue(result.axis_swap_suspected)
        self.assertTrue(result.requires_confirmation)

    def test_indiana_utm(self):
        self.assertEqual(utm_authid(-86.1, 40.2), "EPSG:32616")
        self.assertEqual(choose_analysis_crs("EPSG:4326", (-86.1, 40.2)), "EPSG:32616")

    def test_implausible_field_extent(self):
        errors = validate_coordinate_extent(0, 0, 150_000, 100)
        self.assertIn("transformed extent is implausibly large for a single field", errors)


if __name__ == "__main__":
    unittest.main()
