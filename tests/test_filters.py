# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for individual filters and the cleaning pipeline engine."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from yield_data_cleaner.core.filter_engine import run_cleaning_filters
from yield_data_cleaner.core.recipe import CleaningRecipe
from yield_data_cleaner.filters.motion import evaluate_motion_filters
from yield_data_cleaner.filters.pass_edge import evaluate_pass_edge_filters
from yield_data_cleaner.filters.quality import evaluate_quality_filters
from yield_data_cleaner.filters.ranges import evaluate_range_filters
from yield_data_cleaner.filters.swath import evaluate_swath_filters


class FilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recipe = CleaningRecipe(
            crop_code="corn",
            min_speed_m_s=0.5,
            max_speed_m_s=4.0,
            max_speed_change_m_s=1.0,
            min_swath_width_m=1.0,
            pass_start_count=2,
            pass_end_count=2,
            min_yield_kg_ha=500.0,
            max_yield_kg_ha=20000.0,
            min_moisture_pct=10.0,
            max_moisture_pct=30.0,
        )

    def test_quality_filters(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = [
            {"x": None, "y": None, "timestamp_utc": t0.isoformat()},  # invalid_geometry
            {
                "x": 10.0,
                "y": 20.0,
                "yield_wet_mass_area": float("nan"),
                "timestamp_utc": t0.isoformat(),
            },  # invalid_numeric
            {"x": 10.0, "y": 20.0, "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat()},
            {
                "x": 10.0,
                "y": 20.0,
                "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat(),
            },  # duplicate_observation
        ]
        reasons = evaluate_quality_filters(obs, self.recipe)
        self.assertIn("invalid_geometry", reasons[0])
        self.assertIn("invalid_numeric", reasons[1])
        self.assertIn("duplicate_observation", reasons[3])

    def test_motion_filters(self) -> None:
        obs = [
            {"header_engaged": False, "speed_m_s": 2.0},  # header_disengaged
            {"header_engaged": True, "speed_m_s": 0.2},  # speed_below_min
            {"header_engaged": True, "speed_m_s": 5.5},  # speed_above_max
            {"header_engaged": True, "speed_m_s": 2.0, "pass_id": "1"},
            {
                "header_engaged": True,
                "speed_m_s": 3.8,
                "pass_id": "1",
            },  # speed_change (delta=1.8 > 1.0)
        ]
        reasons = evaluate_motion_filters(obs, self.recipe)
        self.assertIn("header_disengaged", reasons[0])
        self.assertIn("speed_below_min", reasons[1])
        self.assertIn("speed_above_max", reasons[2])
        self.assertIn("speed_change", reasons[4])

    def test_swath_filters(self) -> None:
        obs = [
            {"swath_width_m": 0.5},  # swath_below_min
            {"swath_width_m": 6.0},  # ok
        ]
        reasons = evaluate_swath_filters(obs, self.recipe)
        self.assertIn("swath_below_min", reasons[0])
        self.assertEqual(len(reasons[1]), 0)

    def test_pass_edge_filters(self) -> None:
        obs = [
            {"pass_id": "1"},  # index 0: pass_start
            {"pass_id": "1"},  # index 1: pass_start
            {"pass_id": "1"},  # index 2: inside
            {"pass_id": "1"},  # index 3: pass_end
            {"pass_id": "1"},  # index 4: pass_end
        ]
        reasons = evaluate_pass_edge_filters(obs, self.recipe)
        self.assertIn("pass_start", reasons[0])
        self.assertIn("pass_start", reasons[1])
        self.assertEqual(len(reasons[2]), 0)
        self.assertIn("pass_end", reasons[3])
        self.assertIn("pass_end", reasons[4])

    def test_ranges_filters(self) -> None:
        obs = [
            {"yield_wet_mass_area": 200.0, "moisture_pct": 15.0},  # yield_below_min
            {"yield_wet_mass_area": 25000.0, "moisture_pct": 15.0},  # yield_above_max
            {"yield_wet_mass_area": 10000.0, "moisture_pct": 8.0},  # moisture_below_min
            {"yield_wet_mass_area": 10000.0, "moisture_pct": 35.0},  # moisture_above_max
            {"yield_wet_mass_area": 10000.0, "moisture_pct": 15.0},  # accepted
        ]
        reasons = evaluate_range_filters(obs, self.recipe)
        self.assertIn("yield_below_min", reasons[0])
        self.assertIn("yield_above_max", reasons[1])
        self.assertIn("moisture_below_min", reasons[2])
        self.assertIn("moisture_above_max", reasons[3])
        self.assertEqual(len(reasons[4]), 0)

    def test_full_cleaning_pipeline(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = [
            # 5 good observations in pass 1
            {
                "pass_id": "1",
                "x": 0.0,
                "y": 0.0,
                "timestamp_utc": t0.isoformat(),
                "header_engaged": True,
                "speed_m_s": 2.0,
                "swath_width_m": 6.0,
                "yield_wet_mass_area": 10000.0,
                "moisture_pct": 15.0,
            },
            {
                "pass_id": "1",
                "x": 0.0,
                "y": 2.0,
                "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat(),
                "header_engaged": True,
                "speed_m_s": 2.0,
                "swath_width_m": 6.0,
                "yield_wet_mass_area": 10000.0,
                "moisture_pct": 15.0,
            },
            {
                "pass_id": "1",
                "x": 0.0,
                "y": 4.0,
                "timestamp_utc": (t0 + timedelta(seconds=2)).isoformat(),
                "header_engaged": True,
                "speed_m_s": 2.0,
                "swath_width_m": 6.0,
                "yield_wet_mass_area": 10000.0,
                "moisture_pct": 15.0,
            },
            {
                "pass_id": "1",
                "x": 0.0,
                "y": 6.0,
                "timestamp_utc": (t0 + timedelta(seconds=3)).isoformat(),
                "header_engaged": True,
                "speed_m_s": 2.0,
                "swath_width_m": 6.0,
                "yield_wet_mass_area": 10000.0,
                "moisture_pct": 15.0,
            },
            {
                "pass_id": "1",
                "x": 0.0,
                "y": 8.0,
                "timestamp_utc": (t0 + timedelta(seconds=4)).isoformat(),
                "header_engaged": True,
                "speed_m_s": 2.0,
                "swath_width_m": 6.0,
                "yield_wet_mass_area": 10000.0,
                "moisture_pct": 15.0,
            },
        ]
        result = run_cleaning_filters(obs, self.recipe)
        self.assertEqual(result.total_observations, 5)
        # In pass 1 with pass_start_count=2 and pass_end_count=2 on 5 points:
        # idx 0: pass_start -> excluded
        # idx 1: pass_start -> excluded
        # idx 2: middle -> accepted
        # idx 3: pass_end -> excluded
        # idx 4: pass_end -> excluded
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.excluded_count, 4)
        self.assertEqual(result.observation_updates[2]["clean_status"], "accepted")
        self.assertEqual(result.observation_updates[0]["clean_status"], "excluded")
        self.assertIn("pass_start", result.observation_updates[0]["filter_reasons"])


if __name__ == "__main__":
    unittest.main()
