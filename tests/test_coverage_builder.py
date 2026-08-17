# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for swath footprint and coverage builder."""

from __future__ import annotations

import unittest

from yield_data_cleaner.boundaries.coverage_builder import (
    build_pass_coverage_footprints,
    build_swath_footprint,
)


class CoverageBuilderTests(unittest.TestCase):
    def test_build_swath_footprint_geometry(self) -> None:
        # Point at origin, heading 0 (North), width 6m, length 2m
        fp = build_swath_footprint(
            x=0.0,
            y=0.0,
            heading_deg=0.0,
            swath_width_m=6.0,
            length_m=2.0,
            obs_id="obs_1",
            pass_id="1",
        )
        self.assertEqual(len(fp.coordinates), 5)  # Closed polygon
        self.assertEqual(fp.coordinates[0], fp.coordinates[-1])
        self.assertAlmostEqual(fp.area_m2, 12.0, places=2)

        feat = fp.to_geojson_feature()
        self.assertEqual(feat["type"], "Feature")
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        self.assertEqual(feat["properties"]["observation_id"], "obs_1")

    def test_build_pass_coverage_footprints(self) -> None:
        obs = [
            {"observation_id": "obs_1", "x": 0.0, "y": 0.0, "heading_deg": 90.0, "swath_width_m": 6.0, "distance_m": 2.0},
            {"observation_id": "obs_2", "x": 2.0, "y": 0.0, "heading_deg": 90.0, "swath_width_m": 6.0, "distance_m": 2.0},
        ]
        fps = build_pass_coverage_footprints(obs)
        self.assertEqual(len(fps), 2)
        self.assertAlmostEqual(fps[0].area_m2, 12.0, places=2)


if __name__ == "__main__":
    unittest.main()
