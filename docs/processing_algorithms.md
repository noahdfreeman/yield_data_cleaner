# QGIS Processing Algorithm Reference

Yield Data Cleaner registers native algorithms in the **QGIS Processing Toolbox** under the `Yield Data Cleaner` provider. These algorithms can be executed in batch mode, run headlessly via Python, or chained into the QGIS Graphical Modeler.

---

## `yield_data_cleaner:clean_yield_data`

Executes the complete, non-destructive agronomic yield data cleaning pipeline.

### Input Parameters

| Parameter Name | Identifier | Type | Description |
| :--- | :--- | :--- | :--- |
| **Input Yield Points** | `INPUT` | `QgsProcessingParameterFeatureSource` | Point vector layer containing raw harvest observations. |
| **Field Boundary** | `BOUNDARY` | `QgsProcessingParameterFeatureSource` | Optional polygon layer representing field boundary. |
| **Crop Profile** | `CROP` | `QgsProcessingParameterEnum` | Crop type (`corn`, `soybean`, `wheat`, `barley`, `oats`, etc.). |
| **Flow Delay (s)** | `FLOW_DELAY` | `QgsProcessingParameterNumber` | Seconds to shift mass flow measurements (default: `10.0`). |
| **Min Speed** | `MIN_SPEED` | `QgsProcessingParameterNumber` | Minimum harvest speed threshold (default: `1.0 mph`). |
| **Max Speed** | `MAX_SPEED` | `QgsProcessingParameterNumber` | Maximum harvest speed threshold (default: `8.0 mph`). |
| **Min Yield** | `MIN_YIELD` | `QgsProcessingParameterNumber` | Minimum plausible dry yield (default: `10.0 bu/ac`). |
| **Max Yield** | `MAX_YIELD` | `QgsProcessingParameterNumber` | Maximum plausible dry yield (default: `350.0 bu/ac`). |
| **Trim Start Pass (s)**| `TRIM_START` | `QgsProcessingParameterNumber` | Seconds trimmed from pass beginning (default: `5.0`). |
| **Trim End Pass (s)** | `TRIM_END` | `QgsProcessingParameterNumber` | Seconds trimmed from pass end (default: `3.0`). |
| **Enable Overlap** | `FILTER_OVERLAP` | `QgsProcessingParameterBoolean` | Exclude overlapping swath passes (default: `True`). |
| **Enable Spatial Outliers**| `FILTER_OUTLIERS` | `QgsProcessingParameterBoolean` | Exclude local spatial outliers (default: `True`). |
| **Grid Size (m)** | `GRID_SIZE` | `QgsProcessingParameterNumber` | Interpolation grid cell size (default: `9.144 m / 30 ft`). |

### Output Destinations

| Output Name | Identifier | Type | Description |
| :--- | :--- | :--- | :--- |
| **Cleaned Yield Layer** | `OUTPUT` | `QgsProcessingParameterFeatureSink` | Point layer containing accepted observations. |
| **Full Audit Layer** | `AUDIT_OUTPUT` | `QgsProcessingParameterFeatureSink` | Complete point layer with all reason codes and flags. |
| **HTML Review File** | `REVIEW_HTML` | `QgsProcessingParameterFileDestination` | Standalone Leaflet HTML review package. |

---

## Python Example (PyQGIS)

```python
import processing

params = {
    'INPUT': 'path/to/raw_harvest.shp',
    'BOUNDARY': 'path/to/field_boundary.shp',
    'CROP': 0, # Corn
    'FLOW_DELAY': 10.0,
    'MIN_SPEED': 1.0,
    'MAX_SPEED': 8.0,
    'MIN_YIELD': 10.0,
    'MAX_YIELD': 320.0,
    'FILTER_OVERLAP': True,
    'FILTER_OUTLIERS': True,
    'GRID_SIZE': 9.144,
    'OUTPUT': 'path/to/cleaned_output.gpkg',
    'REVIEW_HTML': 'path/to/review_report.html'
}

result = processing.run("yield_data_cleaner:clean_yield_data", params)
print("Cleaned yield points saved to:", result['OUTPUT'])
```
