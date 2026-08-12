# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import configparser
import unittest
from pathlib import Path

from yield_data_cleaner.version import VERSION

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "yield_data_cleaner"


class RepositoryStructureTests(unittest.TestCase):
    def test_required_plugin_files(self):
        for relative in (
            "__init__.py",
            "metadata.txt",
            "plugin.py",
            "provider.py",
            "version.py",
            "LICENSE",
        ):
            self.assertTrue((PACKAGE / relative).is_file(), relative)

    def test_metadata_version_and_provider(self):
        parser = configparser.ConfigParser()
        parser.read(PACKAGE / "metadata.txt", encoding="utf-8")
        self.assertEqual(parser.get("general", "version"), VERSION)
        self.assertEqual(parser.get("general", "hasProcessingProvider"), "True")
        self.assertEqual(parser.get("general", "experimental"), "True")
        icon = parser.get("general", "icon")
        self.assertEqual(icon, "resources/icon.png")
        self.assertTrue((PACKAGE / icon).is_file(), icon)
        for key in ("homepage", "repository", "tracker"):
            self.assertTrue(parser.get("general", key).startswith("https://"), key)

    def test_all_python_files_parse_without_bom(self):
        for path in sorted(PACKAGE.rglob("*.py")):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), str(path))
            ast.parse(raw.decode("utf-8"), filename=str(path))

    def test_distributed_python_has_spdx(self):
        for path in sorted(PACKAGE.rglob("*.py")):
            first = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, "# SPDX-License-Identifier: GPL-3.0-or-later", str(path))


if __name__ == "__main__":
    unittest.main()
