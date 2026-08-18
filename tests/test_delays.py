# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for sensor delay shifting and estimation."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from yield_data_cleaner.filters.delays import apply_sensor_delays, estimate_flow_delay


class DelayTests(unittest.TestCase):
    def test_apply_sensor_delays_shifts_values(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        for i in range(10):
            obs.append(
                {
                    "source_index": i,
                    "pass_id": "1",
                    "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                    "yield_wet_mass_area": 5000.0 + (i * 500.0),  # index 0 is 5000, index 2 is 6000
                    "moisture_pct": 15.0 + (i * 0.5),
                }
            )

        # Apply 2 second flow delay (interval is 1.0s, so shift is 2 positions)
        shifted = apply_sensor_delays(obs, flow_delay_s=2.0, moisture_delay_s=0.0)
        self.assertEqual(len(shifted), 10)
        # Position 0 should now have yield from index 2 (6000.0)
        self.assertEqual(shifted[0]["yield_wet_mass_area"], 6000.0)
        # Position 1 should have yield from index 3 (6500.0)
        self.assertEqual(shifted[1]["yield_wet_mass_area"], 6500.0)
        # Last 2 positions should be None
        self.assertIsNone(shifted[8]["yield_wet_mass_area"])
        self.assertIsNone(shifted[9]["yield_wet_mass_area"])

    def test_estimate_flow_delay(self) -> None:
        t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = []
        for i in range(30):
            obs.append(
                {
                    "source_index": i,
                    "pass_id": "1",
                    "timestamp_utc": (t0 + timedelta(seconds=i)).isoformat(),
                    "yield_wet_mass_area": 8000.0,
                }
            )
        result = estimate_flow_delay(obs)
        self.assertIsNotNone(result.estimated_delay_s)
        self.assertIsInstance(result.is_stable, bool)


if __name__ == "__main__":
    unittest.main()
