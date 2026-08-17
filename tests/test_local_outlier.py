# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for robust local spatial outlier detection."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.recipe import CleaningRecipe
from yield_data_cleaner.filters.local_outlier import evaluate_local_outlier_filter


class LocalOutlierTests(unittest.TestCase):
    def test_local_spatial_outlier_flagged(self) -> None:
        recipe = CleaningRecipe(
            filter_local_outlier=True,
            local_outlier_radius_m=25.0,
            local_outlier_std_devs=2.5,
            local_outlier_min_neighbors=5,
        )
        obs = [
            # Cluster of normal points around 8000 kg/ha
            {"source_index": 0, "x": 0.0, "y": 0.0, "yield_wet_mass_area": 8000.0},
            {"source_index": 1, "x": 5.0, "y": 0.0, "yield_wet_mass_area": 8100.0},
            {"source_index": 2, "x": 10.0, "y": 0.0, "yield_wet_mass_area": 7950.0},
            {"source_index": 3, "x": 0.0, "y": 5.0, "yield_wet_mass_area": 8050.0},
            {"source_index": 4, "x": 5.0, "y": 5.0, "yield_wet_mass_area": 8000.0},
            {"source_index": 5, "x": 10.0, "y": 5.0, "yield_wet_mass_area": 7900.0},

            # Point right in the middle with extreme spike (25000 kg/ha)
            {"source_index": 6, "x": 5.0, "y": 2.5, "yield_wet_mass_area": 25000.0},
        ]
        reasons = evaluate_local_outlier_filter(obs, recipe)
        # Point 6 is surrounded by normal points and has an extreme value -> flagged!
        self.assertIn("local_yield_outlier", reasons[6])
        # Point 0 is normal
        self.assertEqual(len(reasons[0]), 0)


if __name__ == "__main__":
    unittest.main()
