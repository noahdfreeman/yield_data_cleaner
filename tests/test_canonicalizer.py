# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.canonicalizer import canonicalize_attributes, stable_observation_id
from yield_data_cleaner.core.mapping_profile import MappingProfile


class CanonicalizerTests(unittest.TestCase):
    def test_imperial_values_convert_to_canonical_si(self):
        source = {
            "Longitude": "-86.1",
            "Latitude": "40.2",
            "Yield": "200",
            "Speed": "5",
            "Width": "30",
            "Moisture": "16.5",
        }
        profile = MappingProfile(
            mapping={
                "x": "Longitude",
                "y": "Latitude",
                "yield_dry_mass_area": "Yield",
                "speed_m_s": "Speed",
                "swath_width_m": "Width",
                "moisture_pct": "Moisture",
            },
            crop_code="corn",
            source_crs="EPSG:4326",
        )
        result = canonicalize_attributes(source, "field.csv", 7, profile)
        self.assertAlmostEqual(result["yield_dry_mass_area"], 12553.533, places=3)
        self.assertAlmostEqual(result["speed_m_s"], 2.2352, places=4)
        self.assertAlmostEqual(result["swath_width_m"], 9.144, places=3)
        self.assertEqual(result["moisture_pct"], 16.5)
        self.assertEqual(result["source_sequence"], 7)
        self.assertEqual(result["clean_status"], "unavailable")

    def test_stable_id_depends_on_source_and_index(self):
        first = stable_observation_id("field.csv", 1)
        self.assertEqual(first, stable_observation_id("field.csv", 1))
        self.assertNotEqual(first, stable_observation_id("field.csv", 2))

    def test_mapping_validation_checks_available_fields(self):
        profile = MappingProfile(mapping={"x": "Missing"}, crop_code="soybean")
        with self.assertRaisesRegex(ValueError, "mapped source columns are missing"):
            canonicalize_attributes({"X": 1}, "field.csv", 0, profile)


if __name__ == "__main__":
    unittest.main()
