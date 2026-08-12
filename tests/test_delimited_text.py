# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from yield_data_cleaner.core.delimited_text import inspect_delimited_file


class DelimitedTextTests(unittest.TestCase):
    def test_inspects_semicolon_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "yield.csv"
            path.write_text(
                "Longitude;Latitude;Yield;Moisture\n-86.1;40.1;200;16\n",
                encoding="utf-8",
            )
            inspection = inspect_delimited_file(path)
            self.assertEqual(inspection.delimiter, ";")
            mapped = {
                item.canonical_field: item.source_column for item in inspection.mapping_suggestions
            }
            self.assertEqual(mapped["x"], "Longitude")
            self.assertEqual(mapped["yield_dry_mass_area"], "Yield")

    def test_binary_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.bin"
            path.write_bytes(b"abc\x00def")
            with self.assertRaisesRegex(ValueError, "binary"):
                inspect_delimited_file(path)

    def test_duplicate_headers_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("x,x\n1,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect_delimited_file(path)


if __name__ == "__main__":
    unittest.main()
