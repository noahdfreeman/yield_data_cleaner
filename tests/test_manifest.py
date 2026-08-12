# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from yield_data_cleaner.core.manifest import build_manifest, file_signature


class ManifestTests(unittest.TestCase):
    def test_file_signature_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_bytes(b"x,y\n1,2\n")
            first = file_signature(path)
            self.assertEqual(first, file_signature(path))
            self.assertEqual(first["size_bytes"], 8)

    def test_preparation_manifest_does_not_claim_cleaning(self):
        manifest = build_manifest(
            "layer",
            "qgis_feature_source",
            "EPSG:4326",
            "EPSG:32616",
            "corn",
            "imperial",
            "automatic",
            10,
        )
        self.assertFalse(manifest["cleaning_applied"])
        self.assertEqual(manifest["operation"], "canonical_preparation_only")


if __name__ == "__main__":
    unittest.main()
