# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from yield_data_cleaner.core.column_detection import detect_columns, suggestions_by_field


class ColumnDetectionTests(unittest.TestCase):
    def test_common_monitor_columns(self):
        columns = [
            "Longitude",
            "Latitude",
            "Dry Yield (bu/ac)",
            "Moisture %",
            "Ground Speed",
            "Swath Width",
        ]
        rows = [
            {
                "Longitude": -86.15,
                "Latitude": 40.25,
                "Dry Yield (bu/ac)": 210.4,
                "Moisture %": 16.1,
                "Ground Speed": 4.7,
                "Swath Width": 30,
            }
        ]
        mapped = suggestions_by_field(detect_columns(columns, rows))
        self.assertEqual(mapped["x"].source_column, "Longitude")
        self.assertEqual(mapped["y"].source_column, "Latitude")
        self.assertEqual(mapped["yield_dry_mass_area"].source_column, "Dry Yield (bu/ac)")
        self.assertEqual(mapped["moisture_pct"].source_column, "Moisture %")
        self.assertEqual(mapped["speed_m_s"].source_column, "Ground Speed")
        self.assertEqual(mapped["swath_width_m"].source_column, "Swath Width")

    def test_non_numeric_sample_reduces_numeric_suggestion(self):
        suggestions = detect_columns(["Yield"], [{"Yield": "unknown"}, {"Yield": "bad"}])
        self.assertEqual(suggestions, [])

    def test_source_column_is_not_assigned_twice(self):
        suggestions = detect_columns(["Time"], [{"Time": "12:00:00"}])
        self.assertEqual(len([item for item in suggestions if item.source_column == "Time"]), 1)

    def test_volumetric_yield_preferred_over_mass_rate(self):
        columns = ["Yld_Mass_D", "Yld_Vol_Dr", "Speed_mph_", "Swth_Wdth_"]
        rows = [
            {
                "Yld_Mass_D": 8760.08,
                "Yld_Vol_Dr": 143.17,
                "Speed_mph_": 2.65,
                "Swth_Wdth_": 30.0,
            },
            {
                "Yld_Mass_D": 10626.33,
                "Yld_Vol_Dr": 173.68,
                "Speed_mph_": 2.70,
                "Swth_Wdth_": 30.0,
            },
        ]
        mapped = suggestions_by_field(detect_columns(columns, rows))
        self.assertEqual(mapped["yield_dry_mass_area"].source_column, "Yld_Vol_Dr")


if __name__ == "__main__":
    unittest.main()
