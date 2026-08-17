# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for standalone HTML review generator."""

from __future__ import annotations

import unittest

from yield_data_cleaner.core.filter_engine import CleaningRunResult
from yield_data_cleaner.core.recipe import CleaningRecipe
from yield_data_cleaner.review.builder import generate_html_review


class ReviewBuilderTests(unittest.TestCase):
    def test_generate_html_review(self) -> None:
        obs = [
            {"observation_id": "obs_1", "x": 500000.0, "y": 4500000.0, "yield_wet_mass_area": 10000.0},
            {"observation_id": "obs_2", "x": 500002.0, "y": 4500000.0, "yield_wet_mass_area": 1000.0},
        ]
        result = CleaningRunResult(
            total_observations=2,
            accepted_count=1,
            excluded_count=1,
            reason_counts={"speed_below_min": 1},
            observation_updates=[
                {"clean_status": "accepted", "filter_reasons": ""},
                {"clean_status": "excluded", "filter_reasons": "speed_below_min"},
            ],
            recipe=CleaningRecipe(crop_code="corn"),
        )

        html_out = generate_html_review(
            run_name="NorthField_Corn_2026",
            field_name="NorthField",
            crop_code="corn",
            unit_profile="imperial",
            observations=obs,
            cleaning_result=result,
            analysis_crs="EPSG:32616",
        )

        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("NorthField", html_out)
        self.assertIn("topBanner", html_out)
        self.assertIn("mapOptionsCard", html_out)
        self.assertIn("leftLayerCard", html_out)
        self.assertIn("swipeDivider", html_out)

    def test_html_escaping_prevents_injection(self) -> None:
        obs = [{"observation_id": "obs_1", "x": 0.0, "y": 0.0, "yield_wet_mass_area": 8000.0}]
        result = CleaningRunResult(
            total_observations=1,
            accepted_count=1,
            excluded_count=0,
            reason_counts={},
            observation_updates=[{"clean_status": "accepted", "filter_reasons": ""}],
            recipe=CleaningRecipe(crop_code="corn"),
        )
        unsafe_name = "<script>alert('xss')</script>"
        html_out = generate_html_review(
            run_name=unsafe_name,
            field_name=unsafe_name,
            crop_code="corn",
            unit_profile="imperial",
            observations=obs,
            cleaning_result=result,
        )
        self.assertNotIn("<script>alert('xss')</script>", html_out)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", html_out)

    def test_raw_attributes_and_interpolated_surface_included(self) -> None:
        obs = [
            {
                "observation_id": "obs_1",
                "x": 500000.0,
                "y": 4500000.0,
                "yield_wet_mass_area": 10000.0,
                "Yld_Vol_Dr": 210.5,
                "Speed_mph_": 4.8,
                "Custom_Elevation": 842.1,
            },
            {
                "observation_id": "obs_2",
                "x": 500020.0,
                "y": 4500020.0,
                "yield_wet_mass_area": 9500.0,
                "Yld_Vol_Dr": 198.2,
                "Speed_mph_": 4.9,
                "Custom_Elevation": 843.0,
            },
            {
                "observation_id": "obs_3",
                "x": 500040.0,
                "y": 4500040.0,
                "yield_wet_mass_area": 9800.0,
                "Yld_Vol_Dr": 204.0,
                "Speed_mph_": 5.0,
                "Custom_Elevation": 841.5,
            },
        ]
        result = CleaningRunResult(
            total_observations=3,
            accepted_count=3,
            excluded_count=0,
            reason_counts={},
            observation_updates=[
                {"clean_status": "accepted", "filter_reasons": ""},
                {"clean_status": "accepted", "filter_reasons": ""},
                {"clean_status": "accepted", "filter_reasons": ""},
            ],
            recipe=CleaningRecipe(crop_code="corn"),
        )

        html_out = generate_html_review(
            run_name="TestField_Corn",
            field_name="TestField",
            crop_code="corn",
            unit_profile="imperial",
            observations=obs,
            cleaning_result=result,
            analysis_crs="EPSG:32616",
            grid_size_ft=30.0,
        )

        # 1. Raw attributes in options dropdown
        self.assertIn("raw:Yld_Vol_Dr", html_out)
        self.assertIn("raw:Speed_mph_", html_out)
        self.assertIn("raw:Custom_Elevation", html_out)

        # 2. Interpolated surface layer in options
        self.assertIn("Cleaned Yield Interpolated Surface (Grid)", html_out)

        # 3. Exactly 3 Basemap options: Hybrid, Satellite, Streets
        self.assertIn('<option value="hybrid" selected>Hybrid</option>', html_out)
        self.assertIn('<option value="satellite">Satellite</option>', html_out)
        self.assertIn('<option value="streets">Streets</option>', html_out)

        # 4. Transportation roads in hybrid provider
        self.assertIn("World_Transportation", html_out)

        # 5. Disable map dragging on slider drag
        self.assertIn("map.dragging.disable()", html_out)

        # 6. No field/crop dropdowns in map options card
        self.assertNotIn('id="fieldSelect"', html_out)
        self.assertNotIn('id="cropSelect"', html_out)

        # 7. No "Fields in run" KPI tile
        self.assertNotIn("Fields in run", html_out)

        # 8. reviewInfoCard is pushed down below zoom controls
        self.assertIn("top: 85px", html_out)

        # 9. Statistical comparison table like in Clean & Review
        self.assertIn("kpi-compare-table", html_out)
        self.assertIn("Mean Yield", html_out)
        self.assertIn("Std Dev (STD)", html_out)
        self.assertIn("Coeff of Variation (CV)", html_out)
        self.assertIn("Observations (N)", html_out)
        self.assertIn("Yield Range", html_out)

        # 10. Expandable Distribution & Classification
        self.assertIn("Distribution &amp; Classification", html_out)
        self.assertIn('id="leftHistSvg"', html_out)
        self.assertIn('id="leftClassMode"', html_out)
        self.assertIn('id="leftClassCount"', html_out)
        self.assertIn("Quantile (Equal Count)", html_out)
        self.assertIn("Equal Interval", html_out)
        self.assertIn("Natural Breaks", html_out)
        self.assertIn("Std Dev", html_out)

        # 11. Field boundary checkbox & layer
        self.assertIn('id="boundaryCheckbox"', html_out)
        self.assertIn("boundaryLayerGroup", html_out)

    def test_interpolated_grid_clipped_to_boundary(self) -> None:
        clean_pts = [
            (40.0, -86.0, 180.0),
            (40.01, -86.0, 190.0),
            (40.0, -85.99, 185.0),
            (40.01, -85.99, 195.0),
        ]
        # Triangular boundary covering only bottom-left half
        bnd_poly = [[(40.0, -86.0), (40.01, -86.0), (40.0, -85.99), (40.0, -86.0)]]
        from yield_data_cleaner.review.builder import generate_interpolated_grid

        grid = generate_interpolated_grid(
            clean_points=clean_pts,
            grid_size_m=50.0,
            boundary_coords=bnd_poly,
        )
        self.assertIsNotNone(grid)
        # Verify that cells outside the polygon are None
        has_none = any(cell is None for row in grid["cells"] for cell in row)
        has_val = any(cell is not None for row in grid["cells"] for cell in row)
        self.assertTrue(has_none)
        self.assertTrue(has_val)

    def test_temporal_and_qdate_objects_serializable(self) -> None:
        import datetime

        class MockQDate:
            def toString(self):
                return "2013-10-24"

        obs = [
            {
                "observation_id": "obs_1",
                "x": 500000.0,
                "y": 4500000.0,
                "yield_wet_mass_area": 10000.0,
                "Harvest_Date": MockQDate(),
                "PyDate": datetime.date(2013, 10, 24),
                "PyDateTime": datetime.datetime(2013, 10, 24, 14, 30, 0),
            }
        ]
        result = CleaningRunResult(
            total_observations=1,
            accepted_count=1,
            excluded_count=0,
            reason_counts={},
            observation_updates=[{"clean_status": "accepted", "filter_reasons": ""}],
            recipe=CleaningRecipe(crop_code="corn"),
        )

        html_out = generate_html_review(
            run_name="TestField_Corn",
            field_name="TestField",
            crop_code="corn",
            unit_profile="imperial",
            observations=obs,
            cleaning_result=result,
            analysis_crs="EPSG:32616",
        )

        self.assertIn("2013-10-24", html_out)

    def test_large_dataset_sampling_and_math(self) -> None:
        # Create a dataset with 30,000 points (exceeding max_display_points of 25,000)
        n = 30000
        obs = [
            {
                "observation_id": f"obs_{i}",
                "x": 500000.0 + (i % 100) * 10,
                "y": 4500000.0 + (i // 100) * 10,
                "yield_wet_mass_area": 9000.0 + (i % 500),
                "Yld_Vol_Dr": 180.0 + (i % 30),
            }
            for i in range(n)
        ]
        updates = [{"clean_status": "accepted", "filter_reasons": ""}] * n
        result = CleaningRunResult(
            total_observations=n,
            accepted_count=n,
            excluded_count=0,
            reason_counts={},
            observation_updates=updates,
            recipe=CleaningRecipe(crop_code="corn"),
        )

        html_out = generate_html_review(
            run_name="BryceFarms_Corn",
            field_name="BryceFarms",
            crop_code="corn",
            unit_profile="imperial",
            observations=obs,
            cleaning_result=result,
            analysis_crs="EPSG:32616",
        )

        self.assertIn("BryceFarms", html_out)
        self.assertIn("30,000", html_out)


if __name__ == "__main__":
    unittest.main()
