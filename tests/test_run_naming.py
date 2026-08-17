# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from yield_data_cleaner.core.run_naming import (
    build_run_stem,
    next_available_run_folder,
    run_file_paths,
    safe_name,
)


class RunNamingTests(unittest.TestCase):
    def test_boundary_crop_and_date_form_readable_stem(self):
        self.assertEqual(
            build_run_stem("Beard BND", "Corn", date(2026, 8, 12)),
            "Beard_BND_corn_2026-08-12",
        )

    def test_stem_with_time(self):
        dt = datetime(2026, 8, 17, 9, 2, 11)
        self.assertEqual(
            build_run_stem("Beard BND", "Corn", dt, include_time=True),
            "Beard_BND_corn_2026-08-17_090211",
        )

    def test_unsafe_name_is_sanitized(self):
        self.assertEqual(safe_name("North / Field: 7"), "North_Field_7")
        self.assertEqual(safe_name(""), "field")

    def test_existing_run_gets_incremented_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            (parent / "field_corn_2026-08-12").mkdir()
            (parent / "field_corn_2026-08-12_02").mkdir()
            self.assertEqual(
                next_available_run_folder(parent, "field_corn_2026-08-12").name,
                "field_corn_2026-08-12_03",
            )

    def test_every_output_includes_run_name(self):
        folder = Path("output") / "Beard_BND_corn_2026-08-12"
        paths = run_file_paths(folder)
        for path in paths.values():
            self.assertTrue(path.name.startswith(folder.name), path)
        self.assertEqual(paths["geopackage"].suffix, ".gpkg")


if __name__ == "__main__":
    unittest.main()
