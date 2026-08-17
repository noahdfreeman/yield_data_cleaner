# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for complete run package generator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from yield_data_cleaner.core.filter_engine import CleaningRunResult
from yield_data_cleaner.core.recipe import CleaningRecipe
from yield_data_cleaner.core.run_package import export_cleaned_csv, write_run_package


class RunPackageTests(unittest.TestCase):
    def test_write_run_package_creates_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "TestField_corn_2026-08-17"
            obs = [
                {"observation_id": "obs_1", "x": 0.0, "y": 0.0, "yield_wet_mass_area": 9000.0},
                {"observation_id": "obs_2", "x": 0.0, "y": 2.0, "yield_wet_mass_area": 100.0},
            ]
            result = CleaningRunResult(
                total_observations=2,
                accepted_count=1,
                excluded_count=1,
                reason_counts={"yield_below_min": 1},
                observation_updates=[
                    {"clean_status": "accepted", "filter_reasons": ""},
                    {"clean_status": "excluded", "filter_reasons": "yield_below_min"},
                ],
                recipe=CleaningRecipe(crop_code="corn"),
            )

            summary = write_run_package(
                output_dir=out_dir,
                run_name="TestField_corn_2026-08-17",
                field_name="TestField",
                crop_code="corn",
                unit_profile="imperial",
                observations=obs,
                cleaning_result=result,
            )

            self.assertTrue(Path(summary.manifest_path).exists())
            self.assertTrue(Path(summary.recipe_path).exists())
            self.assertTrue(Path(summary.mapping_path).exists())
            self.assertTrue(Path(summary.summary_csv_path).exists())
            self.assertTrue(Path(summary.review_html_path).exists())
            self.assertTrue(Path(summary.run_log_path).exists())

    def test_export_cleaned_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "cleaned.csv"
            obs = [
                {"observation_id": "obs_1", "x": 0.0, "y": 0.0, "yield_wet_mass_area": 9000.0},
                {"observation_id": "obs_2", "x": 0.0, "y": 2.0, "yield_wet_mass_area": 100.0},
            ]
            result = CleaningRunResult(
                total_observations=2,
                accepted_count=1,
                excluded_count=1,
                reason_counts={"yield_below_min": 1},
                observation_updates=[
                    {"clean_status": "accepted", "filter_reasons": ""},
                    {"clean_status": "excluded", "filter_reasons": "yield_below_min"},
                ],
            )
            count = export_cleaned_csv(csv_path, obs, result)
            self.assertEqual(count, 1)
            self.assertTrue(csv_path.exists())
            content = csv_path.read_text(encoding="utf-8")
            self.assertIn("obs_1", content)
            self.assertNotIn("obs_2", content)


if __name__ == "__main__":
    unittest.main()
