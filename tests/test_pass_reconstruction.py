# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for harvest pass reconstruction and validation."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from yield_data_cleaner.core.pass_reconstruction import (
    PassReconstructionConfig,
    calculate_bearing,
    euclidean_distance,
    heading_difference,
    reconstruct_passes,
    validate_source_passes,
)


class PassReconstructionTests(unittest.TestCase):
    """Tests for pure-Python pass reconstruction algorithms."""

    def test_bearing_and_heading_difference(self) -> None:
        # North
        self.assertAlmostEqual(calculate_bearing((0.0, 0.0), (0.0, 10.0)), 0.0, places=3)
        # East
        self.assertAlmostEqual(calculate_bearing((0.0, 0.0), (10.0, 0.0)), 90.0, places=3)
        # South
        self.assertAlmostEqual(calculate_bearing((0.0, 0.0), (0.0, -10.0)), 180.0, places=3)
        # West
        self.assertAlmostEqual(calculate_bearing((0.0, 0.0), (-10.0, 0.0)), 270.0, places=3)

        # Heading difference across 0/360 boundary
        self.assertAlmostEqual(heading_difference(355.0, 5.0), 10.0, places=3)
        self.assertAlmostEqual(heading_difference(10.0, 350.0), 20.0, places=3)
        self.assertAlmostEqual(heading_difference(90.0, 270.0), 180.0, places=3)

    def test_straight_continuous_pass(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        for i in range(10):
            obs.append({
                "source_index": i,
                "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                "x": 500000.0 + (i * 2.0),
                "y": 4500000.0,
                "heading_deg": 90.0,
                "speed_m_s": 2.0,
                "header_engaged": True,
            })

        result = reconstruct_passes(obs)
        self.assertEqual(result.total_passes, 1)
        self.assertEqual(result.passes[0].point_count, 10)
        self.assertAlmostEqual(result.passes[0].length_m, 18.0, places=2)
        self.assertAlmostEqual(result.passes[0].mean_heading_deg, 90.0, places=1)
        self.assertEqual(result.passes[0].pass_source, "reconstructed")
        self.assertGreaterEqual(result.passes[0].confidence, 0.8)

        # Check observation updates
        self.assertEqual(len(result.observation_updates), 10)
        for update in result.observation_updates:
            self.assertEqual(update["pass_id"], "1")
            self.assertEqual(update["pass_source"], "reconstructed")

    def test_turn_detection_split(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        # Pass 1: heading East
        for i in range(6):
            obs.append({
                "source_index": i,
                "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                "x": 500000.0 + (i * 2.0),
                "y": 4500000.0,
                "heading_deg": 90.0,
                "header_engaged": True,
            })
        # Pass 2: heading West (180 degree turn after headland)
        for i in range(6, 12):
            obs.append({
                "source_index": i,
                "timestamp_utc": (t0 + timedelta(seconds=i + 5)).isoformat(),
                "x": 500000.0 + ((11 - i) * 2.0),
                "y": 4500010.0,
                "heading_deg": 270.0,
                "header_engaged": True,
            })

        result = reconstruct_passes(obs)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.split_reason_counts.get("turn"), 1)
        self.assertEqual(result.passes[0].pass_id, "1")
        self.assertEqual(result.passes[1].pass_id, "2")
        self.assertAlmostEqual(result.passes[0].mean_heading_deg, 90.0, places=1)
        self.assertAlmostEqual(result.passes[1].mean_heading_deg, 270.0, places=1)

    def test_time_gap_split(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        # Segment 1
        for i in range(5):
            obs.append({
                "source_index": i,
                "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                "x": 500000.0,
                "y": 4500000.0 + (i * 2.0),
                "heading_deg": 0.0,
            })
        # Segment 2 (after 10 minute stop)
        t1 = t0 + timedelta(minutes=10)
        for i in range(5):
            obs.append({
                "source_index": i + 5,
                "timestamp_utc": (t1 + timedelta(seconds=i)).isoformat(),
                "x": 500000.0,
                "y": 4500010.0 + (i * 2.0),
                "heading_deg": 0.0,
            })

        config = PassReconstructionConfig(max_time_gap_s=30.0)
        result = reconstruct_passes(obs, config)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.split_reason_counts.get("time_gap"), 1)

    def test_distance_jump_split(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        # Segment 1
        for i in range(5):
            obs.append({
                "source_index": i,
                "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                "x": 500000.0,
                "y": 4500000.0 + (i * 2.0),
                "heading_deg": 0.0,
            })
        # Segment 2 (100m away in next continuous second)
        for i in range(5):
            obs.append({
                "source_index": i + 5,
                "timestamp_utc": (t0 + timedelta(seconds=i + 5)).isoformat(),
                "x": 500000.0,
                "y": 4500100.0 + (i * 2.0),
                "heading_deg": 0.0,
            })

        config = PassReconstructionConfig(max_distance_gap_m=30.0)
        result = reconstruct_passes(obs, config)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.split_reason_counts.get("distance_gap"), 1)

    def test_header_disengage_split(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = [
            {"source_index": 0, "timestamp_utc": (t0 + timedelta(seconds=0)).isoformat(), "x": 0.0, "y": 0.0, "header_engaged": True, "heading_deg": 0.0},
            {"source_index": 1, "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat(), "x": 0.0, "y": 2.0, "header_engaged": True, "heading_deg": 0.0},
            {"source_index": 2, "timestamp_utc": (t0 + timedelta(seconds=2)).isoformat(), "x": 0.0, "y": 4.0, "header_engaged": True, "heading_deg": 0.0},
            {"source_index": 3, "timestamp_utc": (t0 + timedelta(seconds=3)).isoformat(), "x": 0.0, "y": 6.0, "header_engaged": False, "heading_deg": 0.0},
            {"source_index": 4, "timestamp_utc": (t0 + timedelta(seconds=4)).isoformat(), "x": 0.0, "y": 8.0, "header_engaged": True, "heading_deg": 0.0},
            {"source_index": 5, "timestamp_utc": (t0 + timedelta(seconds=5)).isoformat(), "x": 0.0, "y": 10.0, "header_engaged": True, "heading_deg": 0.0},
            {"source_index": 6, "timestamp_utc": (t0 + timedelta(seconds=6)).isoformat(), "x": 0.0, "y": 12.0, "header_engaged": True, "heading_deg": 0.0},
        ]
        config = PassReconstructionConfig(split_on_header_disengage=True)
        result = reconstruct_passes(obs, config)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.split_reason_counts.get("header_lift"), 1)

    def test_multiple_machine_ids(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = [
            {"source_index": 0, "timestamp_utc": (t0 + timedelta(seconds=0)).isoformat(), "x": 0.0, "y": 0.0, "machine_id": "Combine_A", "heading_deg": 0.0},
            {"source_index": 1, "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat(), "x": 0.0, "y": 2.0, "machine_id": "Combine_A", "heading_deg": 0.0},
            {"source_index": 2, "timestamp_utc": (t0 + timedelta(seconds=2)).isoformat(), "x": 0.0, "y": 4.0, "machine_id": "Combine_A", "heading_deg": 0.0},
            {"source_index": 3, "timestamp_utc": (t0 + timedelta(seconds=3)).isoformat(), "x": 10.0, "y": 0.0, "machine_id": "Combine_B", "heading_deg": 0.0},
            {"source_index": 4, "timestamp_utc": (t0 + timedelta(seconds=4)).isoformat(), "x": 10.0, "y": 2.0, "machine_id": "Combine_B", "heading_deg": 0.0},
            {"source_index": 5, "timestamp_utc": (t0 + timedelta(seconds=5)).isoformat(), "x": 10.0, "y": 4.0, "machine_id": "Combine_B", "heading_deg": 0.0},
        ]
        result = reconstruct_passes(obs)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.split_reason_counts.get("machine_change"), 1)

    def test_heading_estimation_when_missing(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = [
            {"source_index": 0, "timestamp_utc": (t0 + timedelta(seconds=0)).isoformat(), "x": 0.0, "y": 0.0},
            {"source_index": 1, "timestamp_utc": (t0 + timedelta(seconds=1)).isoformat(), "x": 10.0, "y": 0.0},
            {"source_index": 2, "timestamp_utc": (t0 + timedelta(seconds=2)).isoformat(), "x": 20.0, "y": 0.0},
            {"source_index": 3, "timestamp_utc": (t0 + timedelta(seconds=3)).isoformat(), "x": 30.0, "y": 0.0},
        ]
        result = reconstruct_passes(obs)
        self.assertEqual(result.total_passes, 1)
        # Heading moving eastward along X should be approximately 90 degrees
        self.assertAlmostEqual(result.passes[0].mean_heading_deg, 90.0, places=1)

    def test_source_pass_validation(self) -> None:
        obs = [
            {"source_index": 0, "source_pass_id": "101", "x": 0.0, "y": 0.0, "heading_deg": 0.0},
            {"source_index": 1, "source_pass_id": "101", "x": 0.0, "y": 2.0, "heading_deg": 0.0},
            {"source_index": 2, "source_pass_id": "101", "x": 0.0, "y": 4.0, "heading_deg": 0.0},
            {"source_index": 3, "source_pass_id": "102", "x": 10.0, "y": 0.0, "heading_deg": 0.0},
            {"source_index": 4, "source_pass_id": "102", "x": 10.0, "y": 2.0, "heading_deg": 0.0},
            {"source_index": 5, "source_pass_id": "102", "x": 10.0, "y": 4.0, "heading_deg": 0.0},
        ]
        result = validate_source_passes(obs)
        self.assertEqual(result.total_passes, 2)
        self.assertEqual(result.passes[0].pass_id, "101")
        self.assertEqual(result.passes[0].pass_source, "source")
        self.assertEqual(result.passes[1].pass_id, "102")
        self.assertEqual(result.passes[1].pass_source, "source")

    def test_empty_observations(self) -> None:
        result = reconstruct_passes([])
        self.assertEqual(result.total_passes, 0)
        self.assertEqual(len(result.passes), 0)


if __name__ == "__main__":
    unittest.main()
