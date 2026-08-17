# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.canonical_schema import (
    CanonicalObservation,
    CrsConfidence,
    source_attribute_collisions,
    validate_observation,
)


class CanonicalSchemaTests(unittest.TestCase):
    def test_valid_minimal_observation(self):
        observation = CanonicalObservation(
            observation_id="run-1:0",
            source_index=0,
            source_name="yield.csv",
            source_sequence=0,
            crs_confidence=CrsConfidence.USER_CONFIRMED,
        )
        self.assertEqual(validate_observation(observation), [])
        self.assertEqual(observation.to_dict()["crs_confidence"], "user_confirmed")

    def test_missing_order_is_invalid(self):
        observation = CanonicalObservation("id", 0, "yield.csv")
        self.assertIn(
            "timestamp_utc or source_sequence is required", validate_observation(observation)
        )

    def test_source_collision_detection(self):
        self.assertEqual(
            source_attribute_collisions({"speed_m_s": 1, "Vendor": "x"}), ("speed_m_s",)
        )
        self.assertEqual(
            source_attribute_collisions({"DURATION_S": 1.0, "Yield_Wet_Mass_Area": 5000.0, "Vendor": "x"}),
            ("DURATION_S", "Yield_Wet_Mass_Area"),
        )


if __name__ == "__main__":
    unittest.main()
