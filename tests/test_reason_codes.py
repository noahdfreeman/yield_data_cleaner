# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.reason_codes import REASON_CODES, REASON_CODE_REGISTRY


class ReasonCodeTests(unittest.TestCase):
    def test_codes_are_unique_lowercase_identifiers(self):
        self.assertEqual(len(REASON_CODES), len(REASON_CODE_REGISTRY))
        for item in REASON_CODES:
            self.assertRegex(item.code, r"^[a-z][a-z0-9_]*$")

    def test_required_non_destructive_codes_exist(self):
        for code in ("outside_boundary", "manual_exclude", "manual_restore"):
            self.assertIn(code, REASON_CODE_REGISTRY)


if __name__ == "__main__":
    unittest.main()
