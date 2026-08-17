# Output Data Schema & Reason Codes

Every cleaning run writes an auditable data package containing the cleaned dataset, full audit history, run configuration recipe, and execution manifest.

---

## GeoPackage Layers (`<run>_yield_data.gpkg`)

| Layer Name | Geometry | Purpose |
| :--- | :--- | :--- |
| `cleaned_observations` | `Point` | Accepted harvest points with standardized dry yield, moisture, speed, and swath. |
| `audit_observations` | `Point` | All observations (accepted + excluded) with `clean_status` and `exclude_reasons`. |
| `field_boundary` | `Polygon` | Active field boundary polygon used during cleaning. |
| `harvest_passes` | `LineString` | Reconstructed pass centerlines with heading and pass confidence. |
| `harvest_coverage` | `MultiPolygon` | Continuous swath cutting footprint polygons. |

---

## Canonical Field Definitions

| Field Name | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `obs_id` | Integer | — | Unique sequence identifier for the observation point. |
| `dry_yield` | Double | bu/ac (or t/ha) | Standardized dry yield value. |
| `moisture` | Double | % | Harvest moisture percentage. |
| `speed` | Double | mph (or km/h) | Ground operating speed. |
| `swath_width` | Double | ft (or m) | Operating header width. |
| `pass_id` | Integer | — | Assigned harvest pass identifier. |
| `timestamp` | String/DateTime | ISO 8601 | Observation recording time. |
| `clean_status` | String | — | `'accepted'` or `'excluded'`. |
| `exclude_reasons` | String | — | Comma-separated list of reason codes. |
| `source_index` | Integer | — | 0-based index linking directly back to the original source row. |

---

## Stable Reason Code Registry

| Reason Code | Category | Explanation |
| :--- | :--- | :--- |
| `OUTSIDE_BOUNDARY` | Boundary | Observation falls outside the confirmed field polygon. |
| `SPEED_MIN` | Motion | Combine speed below minimum harvesting threshold ($< 1.0\text{ mph}$). |
| `SPEED_MAX` | Motion | Combine speed above maximum harvesting threshold ($> 8.0\text{ mph}$). |
| `SPEED_RAPID_CHANGE` | Motion | Instantaneous acceleration/deceleration exceeding limit. |
| `SWATH_MIN` / `SWATH_MAX` | Header | Swath width is zero, negative, or exceeds header width. |
| `HEADER_UP` | Header | Header switch was in the raised / disengaged position. |
| `PASS_START` / `PASS_END` | Pass | Point within the initial ramp-up or ending ramp-down window of a pass. |
| `YIELD_RANGE_LOW` | Biological | Yield value below crop minimum threshold. |
| `YIELD_RANGE_HIGH` | Biological | Yield value above crop maximum threshold. |
| `MOISTURE_RANGE_LOW` | Sensor | Moisture reading below valid sensor threshold. |
| `MOISTURE_RANGE_HIGH` | Sensor | Moisture reading above valid sensor threshold. |
| `OVERLAP` | Spatial | Point location previously harvested by an earlier pass. |
| `LOCAL_OUTLIER` | Spatial | Statistically significant anomaly relative to local spatial neighborhood. |
| `MANUAL_EXCLUDED` | Manual | Point manually selected and excluded by the user. |
