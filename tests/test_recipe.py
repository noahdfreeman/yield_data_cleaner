# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for cleaning recipe contracts and serialization."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.recipe import CleaningRecipe, default_recipe_for_crop


class CleaningRecipeTests(unittest.TestCase):
    def test_default_crop_recipes(self) -> None:
        corn_recipe = default_recipe_for_crop("corn")
        self.assertEqual(corn_recipe.crop_code, "corn")
        self.assertGreater(corn_recipe.max_yield_kg_ha, 20000.0)

        soy_recipe = default_recipe_for_crop("soybean")
        self.assertEqual(soy_recipe.crop_code, "soybean")
        self.assertLess(soy_recipe.max_yield_kg_ha, 10000.0)

        wheat_recipe = default_recipe_for_crop("wheat")
        self.assertEqual(wheat_recipe.crop_code, "wheat")

    def test_json_round_trip(self) -> None:
        recipe = CleaningRecipe(
            crop_code="corn",
            min_speed_m_s=0.5,
            max_speed_m_s=4.0,
            pass_start_count=3,
        )
        json_text = recipe.to_json()
        restored = CleaningRecipe.from_json(json_text)
        self.assertEqual(restored.crop_code, "corn")
        self.assertEqual(restored.min_speed_m_s, 0.5)
        self.assertEqual(restored.max_speed_m_s, 4.0)
        self.assertEqual(restored.pass_start_count, 3)
        self.assertEqual(restored.schema_version, "1.0.0")

    def test_recipe_compatibility_aliases(self) -> None:
        recipe = default_recipe_for_crop("corn")
        self.assertEqual(recipe.pass_edge_start_trim_s, float(recipe.pass_start_count))
        self.assertEqual(recipe.pass_edge_end_trim_s, float(recipe.pass_end_count))
        self.assertEqual(recipe.speed_min_m_s, recipe.min_speed_m_s)
        self.assertEqual(recipe.speed_max_m_s, recipe.max_speed_m_s)
        self.assertEqual(recipe.yield_min_dry_mass_area, recipe.min_yield_kg_ha)
        self.assertEqual(recipe.yield_max_dry_mass_area, recipe.max_yield_kg_ha)
        self.assertEqual(recipe.overlap_filter_enabled, recipe.filter_overlap)
        self.assertEqual(recipe.spatial_outlier_enabled, recipe.filter_local_outlier)
        self.assertEqual(recipe.spatial_outlier_radius_m, recipe.local_outlier_radius_m)
        self.assertEqual(recipe.spatial_outlier_stds, recipe.local_outlier_std_devs)


if __name__ == "__main__":
    unittest.main()
