# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for swath coverage overlap detection."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.recipe import CleaningRecipe
from yield_data_cleaner.filters.overlap import evaluate_overlap_filter


class OverlapTests(unittest.TestCase):
    def test_overlap_detected_across_different_passes(self) -> None:
        recipe = CleaningRecipe(filter_overlap=True, overlap_distance_threshold_m=3.0)
        obs = [
            # Pass 1
            {"source_index": 0, "pass_id": "1", "x": 0.0, "y": 0.0},
            {"source_index": 1, "pass_id": "1", "x": 0.0, "y": 5.0},
            {"source_index": 2, "pass_id": "1", "x": 0.0, "y": 10.0},
            # Pass 2 (Headland cut intersecting Pass 1 at y=5.0)
            {"source_index": 3, "pass_id": "2", "x": 20.0, "y": 5.0},
            {
                "source_index": 4,
                "pass_id": "2",
                "x": 0.5,
                "y": 5.0,
            },  # Intersects (dist=0.5m < 3.0m) -> overlap!
            {"source_index": 5, "pass_id": "2", "x": -20.0, "y": 5.0},
        ]
        reasons = evaluate_overlap_filter(obs, recipe)
        self.assertEqual(len(reasons[0]), 0)
        self.assertEqual(len(reasons[1]), 0)
        self.assertEqual(len(reasons[2]), 0)
        self.assertEqual(len(reasons[3]), 0)
        self.assertIn("harvest_overlap", reasons[4])
        self.assertEqual(len(reasons[5]), 0)


if __name__ == "__main__":
    unittest.main()
