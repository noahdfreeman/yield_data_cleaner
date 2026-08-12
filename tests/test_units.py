# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.crop_profiles import crop_profile
from yield_data_cleaner.core.units import (
    adjust_yield_for_moisture,
    bushels_per_acre_to_kg_per_hectare,
    kg_per_hectare_to_bushels_per_acre,
    m_s_to_mph,
    mph_to_m_s,
)


class UnitConversionTests(unittest.TestCase):
    def test_crop_profiles(self):
        self.assertEqual(crop_profile("corn").test_weight_lb_per_bushel, 56.0)
        self.assertEqual(crop_profile("soybean").standard_moisture_pct, 13.0)
        self.assertEqual(crop_profile("wheat").standard_moisture_pct, 13.5)

    def test_bushel_mass_round_trip(self):
        original = 215.75
        metric = bushels_per_acre_to_kg_per_hectare(original, 56.0)
        self.assertAlmostEqual(kg_per_hectare_to_bushels_per_acre(metric, 56.0), original, places=9)

    def test_speed_round_trip(self):
        self.assertAlmostEqual(m_s_to_mph(mph_to_m_s(4.8)), 4.8, places=12)

    def test_moisture_adjustment_conserves_dry_matter(self):
        adjusted = adjust_yield_for_moisture(200.0, 20.0, 15.5)
        self.assertAlmostEqual(adjusted * 0.845, 200.0 * 0.80, places=9)

    def test_invalid_moisture_rejected(self):
        with self.assertRaises(ValueError):
            adjust_yield_for_moisture(200, 100, 15.5)


if __name__ == "__main__":
    unittest.main()
