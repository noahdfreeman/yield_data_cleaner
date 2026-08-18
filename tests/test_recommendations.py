# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for automated threshold recommendations."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.recommendations import generate_recommendations


class RecommendationTests(unittest.TestCase):
    def test_generate_recommendations(self) -> None:
        obs = []
        for i in range(100):
            obs.append(
                {
                    "yield_wet_mass_area": 8000.0 + (i * 20.0),  # 8000 to 9980 kg/ha
                    "speed_m_s": 1.5 + (i * 0.01),  # 1.5 to 2.49 m/s
                    "moisture_pct": 14.0 + (i * 0.05),  # 14.0 to 18.95%
                    "swath_width_m": 6.0,
                }
            )

        report = generate_recommendations(obs, crop_code="corn")
        self.assertEqual(report.total_observations, 100)
        self.assertIn("min_yield_kg_ha", report.recommendations)
        self.assertIn("max_yield_kg_ha", report.recommendations)
        self.assertIn("min_speed_m_s", report.recommendations)
        self.assertIn("max_speed_m_s", report.recommendations)
        self.assertIn("min_moisture_pct", report.recommendations)

        # Check recommended values are reasonable
        self.assertGreater(report.recommended_recipe.min_yield_kg_ha, 0.0)
        self.assertGreater(
            report.recommended_recipe.max_yield_kg_ha, report.recommended_recipe.min_yield_kg_ha
        )
        self.assertGreater(
            report.recommended_recipe.max_speed_m_s, report.recommended_recipe.min_speed_m_s
        )

    def test_empty_dataset_recommendations(self) -> None:
        report = generate_recommendations([], crop_code="soybean")
        self.assertEqual(report.total_observations, 0)
        self.assertEqual(report.crop_code, "soybean")
        self.assertEqual(len(report.recommendations), 0)


if __name__ == "__main__":
    unittest.main()
