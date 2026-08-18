# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for AgGateway ADAPT Standard export and import."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from yield_data_cleaner.core.filter_engine import CleaningRunResult
from yield_data_cleaner.exporters.adapt_standard import export_adapt_standard_package
from yield_data_cleaner.importers.adapt_standard import import_adapt_standard_package


class AdaptStandardTests(unittest.TestCase):
    def test_export_and_import_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_dir = Path(temp_dir) / "FieldA_Corn_ADAPT"
            obs = [
                {
                    "observation_id": "obs_1",
                    "pass_id": "1",
                    "x": 500000.0,
                    "y": 4500000.0,
                    "yield_wet_mass_area": 9000.0,
                    "moisture_pct": 15.0,
                    "swath_width_m": 6.0,
                    "distance_m": 2.0,
                },
                {
                    "observation_id": "obs_2",
                    "pass_id": "1",
                    "x": 500002.0,
                    "y": 4500000.0,
                    "yield_wet_mass_area": 9100.0,
                    "moisture_pct": 15.0,
                    "swath_width_m": 6.0,
                    "distance_m": 2.0,
                },
                {
                    "observation_id": "obs_3",
                    "pass_id": "1",
                    "x": 500004.0,
                    "y": 4500000.0,
                    "yield_wet_mass_area": 100.0,
                    "moisture_pct": 15.0,
                    "swath_width_m": 6.0,
                    "distance_m": 2.0,
                },
            ]
            cleaning_result = CleaningRunResult(
                total_observations=3,
                accepted_count=2,
                excluded_count=1,
                reason_counts={"yield_below_min": 1},
                observation_updates=[
                    {"clean_status": "accepted"},
                    {"clean_status": "accepted"},
                    {"clean_status": "excluded"},
                ],
            )

            summary = export_adapt_standard_package(
                target_dir=pkg_dir,
                field_name="FieldA",
                crop_code="corn",
                observations=obs,
                cleaning_result=cleaning_result,
                grower_name="Acme Farms",
                farm_name="Home Farm",
            )

            self.assertEqual(summary.accepted_features_count, 2)
            self.assertTrue(Path(summary.manifest_path).exists())
            self.assertTrue(Path(summary.context_path).exists())
            self.assertTrue(Path(summary.logged_data_path).exists())
            self.assertTrue(Path(summary.coverage_path).exists())

            # Now test import
            imported = import_adapt_standard_package(pkg_dir)
            self.assertEqual(imported.field_name, "FieldA")
            self.assertEqual(imported.crop_code, "corn")
            self.assertEqual(imported.grower_name, "Acme Farms")
            self.assertEqual(len(imported.observations), 2)


if __name__ == "__main__":
    unittest.main()
