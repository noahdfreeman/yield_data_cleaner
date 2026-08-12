# SPDX-License-Identifier: GPL-3.0-or-later

import json
import tempfile
import unittest
from pathlib import Path

from yield_data_cleaner.core.mapping_profile import (
    MappingProfile,
    load_mapping_profile,
    save_mapping_profile,
)


class MappingProfileTests(unittest.TestCase):
    def test_round_trip(self):
        profile = MappingProfile(
            mapping={"x": "Longitude", "y": "Latitude", "yield_dry_mass_area": "Yield"},
            crop_code="corn",
            source_crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = save_mapping_profile(profile, Path(directory) / "mapping.json")
            self.assertEqual(load_mapping_profile(path), profile)

    def test_rejects_duplicate_source_mapping(self):
        profile = MappingProfile(
            mapping={"x": "Coordinate", "y": "Coordinate"},
            crop_code="corn",
        )
        self.assertIn("one source column", "; ".join(profile.validate()))

    def test_rejects_oversized_profile_before_json_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_bytes(b" " * 1_048_577)
            with self.assertRaisesRegex(ValueError, "1 MiB"):
                load_mapping_profile(path)

    def test_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "root must be an object"):
                load_mapping_profile(path)


if __name__ == "__main__":
    unittest.main()
