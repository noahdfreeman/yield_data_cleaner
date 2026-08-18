from yield_data_cleaner.core.crop_profiles import available_crops, crop_profile, detect_crop_code
from yield_data_cleaner.core.recipe import default_recipe_for_crop
from yield_data_cleaner.ui.map_styling import get_status_symbol_config, style_layer_for_display


def test_crop_profiles_and_test_weights():
    crops = available_crops()
    assert len(crops) >= 8
    codes = [c.code for c in crops]
    assert "corn" in codes
    assert "soybean" in codes
    assert "wheat" in codes
    assert "barley" in codes
    assert "oats" in codes
    assert "sorghum" in codes
    assert "canola" in codes
    assert "sunflower" in codes

    corn = crop_profile("corn")
    assert corn.test_weight_lb_per_bu == 56.0
    assert corn.standard_moisture_pct == 15.5

    soy = crop_profile("soybean")
    assert soy.test_weight_lb_per_bu == 60.0
    assert soy.standard_moisture_pct == 13.0

    recipe = default_recipe_for_crop("corn")
    assert recipe.crop_code == "corn"
    assert recipe.filter_min_speed is True


def test_crop_auto_detection():
    # Detect from filenames / layer names
    assert detect_crop_code("VenusSW_2011_Soybeans") == "soybean"
    assert (
        detect_crop_code(
            "D:\\Agronomy_Project_Data\\Bryce Farms-All-Rausch Irr. 85-2009-Harvest-Harvest-Corn.shp"
        )
        == "corn"
    )
    assert detect_crop_code("Field10_Winter_Wheat.gpkg") == "wheat"
    assert detect_crop_code("Smith_Canola_2025.csv") == "canola"
    assert detect_crop_code("West_Sorghum.shp") == "sorghum"
    assert detect_crop_code("North_Barley.shp") == "barley"
    assert detect_crop_code("Oats_Block.shp") == "oats"
    assert detect_crop_code("Sunflower_East.geojson") == "sunflower"

    # Detect from sample row attributes
    assert (
        detect_crop_code("Field123", rows=[{"Product": "DKC62-08 Corn", "Yield": 210.5}]) == "corn"
    )
    assert (
        detect_crop_code("Field123", rows=[{"Crop_Type": "Pioneer Soybeans", "Yield": 65.2}])
        == "soybean"
    )
    assert detect_crop_code("UnknownField", rows=[{"Other": "123"}]) is None


def test_map_styling_helpers():
    cfg = get_status_symbol_config()
    assert "accepted" in cfg
    assert "excluded" in cfg
    assert cfg["accepted"]["color"] == "#2e7d32"
    assert cfg["excluded"]["color"] == "#d32f2f"

    # style_layer_for_display handles None gracefully
    assert style_layer_for_display(None, "yield") is False
