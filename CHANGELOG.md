# Changelog

All notable changes to Yield Data Cleaner will be documented here.

## 1.0.1 - 2026-08-18

### Fixed
- **QGIS Plugin Repository Security & Qt6 Compliance**:
  - Resolved Bandit security false positives on harvest pass names, parameters, and HTML templates (0 issues across all scanners).
  - Scoped WKB geometry enums to `QgsWkbTypes.Type.MultiPolygon` and `QgsWkbTypes.Type.Point` for full Qt6 / QGIS 3.34+ / QGIS 4 compatibility.
  - Scoped vertex markers to `QgsVertexMarker.IconType.ICON_BOX`.
  - Removed direct `PyQt5` import fallback in map styling to strictly adhere to official QGIS plugin import standards.

## 1.0.0 - 2026-08-17

### Added
- **Initial Public Release of Yield Data Cleaner**:
  - Full 4-tab guided workflow in QGIS (Input & Mapping, Field Boundary, Prepare Dataset, Clean & Review).
  - Non-destructive filtering pipeline inspired by USDA-ARS Yield Editor 2 with full GeoPackage provenance tracking.
  - Comprehensive column mapping auto-detection, units selector (volume vs mass, imperial/metric), and representative sample extraction.
  - Multi-polygon field boundary derivation, hole removal, vertex densification/simplification, and interactive in-modal vertex editor.
  - Portable, self-contained Leaflet HTML review report with interpolated surface grids, swipe comparison, and embedded plugin logo.
  - AgGateway ADAPT Standard data package export and reusable vendor presets (Ag Leader, John Deere GreenStar, Precision Planting).

## 0.9.37 - 2026-08-17

### Added

- **Official High-Resolution Yield Data Cleaner Logo in HTML Review**:
  - Embedded the official plugin logo as a self-contained base64 Data URI into standalone HTML review reports.
  - Sized the logo significantly larger (48x48 px with subtle border and elevation) and rendered it prominently in the review information header card and header banner bar.

## 0.9.36 - 2026-08-17

### Fixed

- **Pristine State Reset via Reset Tool Action**:
  - Rewrote `_reset_tool` to perform a 100% comprehensive reset across all 4 workflow tabs:
    - **Tab 1**: Restores input source radio buttons, clears file paths, CRS fields, resets crop/unit profiles and test weights, clears all mapping dropdowns, resets sample values to `"—"` and evidence to `"Not inspected"`, clears results summary, and refreshes the QGIS layer list.
    - **Tab 2**: Clears boundary mode, file paths, points file, resets default width, gap closing, concavity parameters, clears and refreshes boundary map canvas, hides in-modal vertex tools and guide labels, and resets action button styles.
    - **Tab 3**: Clears field names, output CRS, run name preview, progress indicators, attribute/ramp dropdowns, and clears the prepared preview map canvas.
    - **Tab 4**: Clears filter results table, post-cleaning preview canvas, disables all export/review buttons, resets recipe filter thresholds to crop defaults, and clears manual exclusion/restoration sets.
    - Automatically switches back to **Tab 1: Input & Mapping** and updates the help guide for a clean restart.

## 0.9.35 - 2026-08-17

### Fixed

- **Exact Multi-Polygon Field Boundary Rendering & IDW Grid Clipping**:
  - Enhanced boundary extraction in `_run_cleaning_pipeline` to iterate through every polygon part and ring (`for ring_pts in poly`) with explicit `QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance().transformContext())`, ensuring multi-part fields, intricate terrace contours, and cutouts are completely preserved.
  - Implemented `parseBoundaryRings` in the Leaflet HTML review builder to support arbitrary nested GeoJSON ring structures without generalization.
  - Removed duplicate `rings` re-initialization in `generate_interpolated_grid` to ensure the IDW surface grid strictly respects all multi-polygon rings.

## 0.9.34 - 2026-08-17

### Fixed

- **Prepared Layer Instantiation**:
  - Restored explicit `prepared_layer` vector layer instantiation from `create_canonical_audit` output in `_run_prepare_dataset`, resolving the `'prepared_layer' is not defined` runtime exception during dataset creation.

## 0.9.33 - 2026-08-17

### Added

- **Reset Tool Action**:
  - Added a dedicated **Reset Tool** button located at the bottom of the inspection dialog adjacent to the Close button.
  - Clears all loaded datasets, column mappings, CRS configuration, boundary preview layers and vertex edits, prepared datasets, and post-cleaning results/canvases, returning to Tab 1 to run a new field immediately.

## 0.9.32 - 2026-08-17

### Fixed

- **Preservation of User-Created/Edited Field Boundaries**:
  - `_run_prepare_dataset` now directly preserves and writes `self.current_preview_boundary_layer` (the simplified/vertex-edited boundary created in Tab 2) to the output GeoPackage, preventing it from being overwritten by raw processing defaults.
  - Coordinate ring extraction accurately extracts multi-polygon/polygon boundaries in WGS84 for exact rendering in the HTML Leaflet review report and precise boundary clipping in the IDW surface grid engine.
- **Swipe Compare Slider Dragging**:
  - Restored clean, real-time dragging for the swipe divider (`swipeDivider`) by handling `pointerdown`, `mousedown`, and `touchstart` with stopPropagation, and removed conflicting `L.DomEvent.disableClickPropagation` intercepts on the divider element.

## 0.9.31 - 2026-08-17

### Fixed

- **Data Opacity Slider Dragging & Event Handling**:
  - Disabled Leaflet click/drag event propagation on all overlay control panels (`mapOptionsCard`, `leftLayerCard`, `rightLayerCard`, `swipeDivider`, `swipeHandle`).
  - Added dedicated pointer/mouse/touch listeners to `opacitySlider` ensuring smooth dragging and instant map layer opacity updates without interference from Leaflet's map pan handler.
- **Guaranteed Field Boundary Rendering & IDW Surface Clipping**:
  - Implemented `compute_points_convex_hull` using pure Python Monotone Chain algorithm so that if an external field boundary is absent or skipped, a 2D boundary polygon is automatically derived from the dataset's coordinates.
  - Passed the guaranteed `effective_boundary` to both the Leaflet boundary renderer and the `generate_interpolated_grid` engine, ensuring the boundary polygon always appears and the interpolated IDW surface grid is strictly clipped to the field perimeter.

## 0.9.30 - 2026-08-17

### Fixed

- **Dynamic Map Classification Mode & Classes**:
  - Implemented `getBreakNorm` mapping so changes to classification modes (Quantile, Equal Interval, Natural Breaks/Jenks, Standard Deviation) and class counts (3 to 8) immediately re-classify and re-color points, interpolated grid surface cells, and SVG distribution histogram bars.
- **Field Boundary Display & Clipping**:
  - Resolved field boundary coordinate extraction from vector layers with WGS84 coordinate transformations and added an automatic boundary envelope fallback derived from observation coordinates.
  - Corrected Leaflet `renderBoundary` parsing to reliably render field boundary polygons on the map canvas.
  - Configured IDW grid interpolation to strictly clip cell values outside the boundary perimeter.

## 0.9.29 - 2026-08-17

### Added

- **Open Run Log Action & Structured Logs**:
  - Added dedicated **Open Run Log** button on Tab 4 (Clean & Review) to view the execution log immediately in the default text editor.
  - Enhanced `{run_name}_run_log.txt` with formatted headers, timestamps, field and crop metadata, coordinate system details, grid resolution, filter exclusion breakdown, and full applied recipe thresholds.

### Fixed

- **HTML Review Map Data Display**:
  - Implemented `renderLayer` and `updateDistribution` functions inside the standalone Leaflet review report, enabling display of cleaned yield points, raw observations, interpolated IDW surfaces, excluded reason codes, SVG distribution histograms, and live classification adjustments.
- **In-Modal Dialog Map Preview**:
  - Constructed the in-modal preview layer directly from prepared observations with live `clean_status` and `filter_reasons` attributes, ensuring the modal canvas immediately renders point styling without GeoPackage table dependency errors.

## 0.9.28 - 2026-08-17

### Added

- **Automatic Crop Auto-Detection (`detect_crop_code`)**:
  - Automatically identifies the crop (Corn, Soybean, Wheat, Barley, Oats, Sorghum, Canola, Sunflower) from the loaded QGIS layer name, local file path, or attribute columns (`Crop`, `Product`, `Commodity`, `Crop_Type`, `Grain`, `Hybrid`).
  - Automatically sets the Crop selector, test weight, standard market moisture, and agronomic filter defaults immediately upon layer selection or file inspection.

### Fixed

- **Large-Dataset Math Scope `UnboundLocalError`**:
  - Removed inner scope `import math` in `generate_html_review` to prevent `UnboundLocalError` when sampling large multi-thousand point datasets (such as 147k point combine monitor files).
- **GeoPackage Pipeline Writing**:
  - Resolved `name 'gpkg' is not defined` error when executing the cleaning pipeline and loading the in-modal preview layer.

## 0.9.27 - 2026-08-17

### Changed

- **Documentation Clean-up**:
  - Removed all icon/emoji decorators across all Markdown documents and `README.md`.
  - Removed "a professional" phrasing from `docs/index.md`.
  - Removed the tip block from `docs/user_guide.md`.

## 0.9.26 - 2026-08-17

### Added

- **Section 17 Complete Documentation Suite**:
  - `docs/index.md`: Documentation hub index.
  - `docs/user_guide.md`: Step-by-step 4-tab workflow guide and Leaflet HTML Data Review manual.
  - `docs/column_mapping.md`: Supported file formats, column detection heuristics, volumetric vs mass calculation formulas, and vendor presets.
  - `docs/crops_and_units.md`: Standard moisture standards, bushel test weights, and conversion mathematics.
  - `docs/filter_methodology.md`: Mathematical and agronomic logic for all 8 cleaning filter families and execution order.
  - `docs/boundary_derivation.md`: Field boundary derivation, swath buffering, vertex smoothing/densification, and clipping rules.
  - `docs/processing_algorithms.md`: QGIS Processing Toolbox parameter and Python scripting reference.
  - `docs/output_schema.md`: GeoPackage tables, canonical attribute definitions, and stable reason code registry.
  - `docs/adapt_interoperability.md`: AgGateway ADAPT Standard JSON and GeoParquet export/import documentation.
  - `docs/validation_report.md`: Scientific validation protocols, mass balance, and runtime performance benchmarks.
  - `docs/compatibility_report.md`: Supported QGIS versions (3.28 LTR through 3.44+), Python, and OS matrix.
  - `docs/privacy_and_security.md`: Local-first architecture, privacy guarantees, and security practices.

## 0.9.25 - 2026-08-17

### Added

- **Clean vs Raw Statistical Comparison Table in HTML Review**: Replaced simple KPI summary blocks with the full 4-column metric audit table (Mean Yield, Std Dev, Coeff of Variation CV, Observations N with excluded %, and Yield Range) comparing Cleaned Dataset vs Raw / Source Data vs Difference.
- **Expandable Variable Distribution Histogram**: Added an interactive expandable drawer on the layer legend card with a real-time SVG frequency histogram colored by the active color ramp and display of variable mean and standard deviation.
- **Dynamic Classification Modes & Class Count Selectors**: Added live classification method controls (`Quantile (Equal Count)`, `Equal Interval`, `Natural Breaks (Jenks)`, `Std Dev`) and class count selector (3 to 8 classes) that re-calculate map point markers, grid surfaces, and histogram bins dynamically in real time.
- **Field Boundary Delivery & Display**: Fixed boundary coordinate passing through the Processing algorithm pipeline so field boundaries render reliably as styled Leaflet vector polygons with a dedicated visibility toggle in the map options panel.

## 0.9.24 - 2026-08-17

### Fixed

- **Point Selection & Live Deletion on Clean & Review Canvas**: Mapped selected features directly by `source_index` instead of internal layer feature IDs, updated the feature attribute table immediately with `clean_status = 'excluded'`, and applied active layer subset filtering (`clean_status = 'accepted'`) so excluded points instantly disappear from the Clean Yield map (and appear in red when viewing Exclusion Status).
- **Field Boundary Checkbox & Vector Polygon in HTML Review**: Added a `Field boundary` toggle checkbox to the top-left map options panel in the HTML review web app and rendered the boundary polygon with a clean styled border (`#1e293b`, dashed).
- **AgGateway ADAPT Standard Export**: Fixed parameter passing (`target_dir=Path(...)` and `cleaning_result`) in `_export_adapt_package` and made `export_adapt_standard_package` accept keyword aliases (`output_dir`, `target_dir`), ensuring export completes smoothly.

## 0.9.23 - 2026-08-17

### Fixed

- **Re-running Filters After Adjusting Parameters**: Wired all recipe spinboxes, checkboxes, and manual delete/restore actions on Tab 4 (`Clean & Review`) to trigger re-execution readiness and keep the `Execute Cleaning Pipeline / Apply Filters` button re-enabled so users can adjust parameters and repeatedly re-filter and update stats/HTML review reports iteratively.
- **Strict Boundary Polygon Clipping for HTML Surface Grid**: Extracted true boundary polygon rings from `current_prepared_boundary_layer` or GeoPackage `field_boundary` with `QgsCoordinateTransform` reprojection into WGS84 and robust Jordan curve ray-casting in `generate_interpolated_grid`, ensuring cells outside the field boundary are masked and clipped to the exact field perimeter.
- **Prevented Main QGIS Canvas Extent Displacement**: Removed hardcoded `iface.mapCanvas().setExtent(...)` calls which caused the main QGIS canvas to jump to (0,0) (the Mediterranean Sea / Gulf of Guinea) when projecting UTM meter extents into default degrees canvas systems.
- **HTML Review UI Overlap Elimination**: Relocated `#reviewInfoCard` from `top: 14px` down to `top: 85px`, eliminating overlap with Leaflet's top-right `+ / -` zoom controls.
- **HTML Review Control Streamlining**: Removed redundant `Field` and `Crop / Season` dropdowns from `#mapOptionsCard` and removed the placeholder `1 FIELDS IN RUN` KPI tile from the summary card.

## 0.9.22 - 2026-08-17

### Fixed

- **`TypeError: Object of type QDate is not JSON serializable`**: Sanitized all QGIS/PyQt temporal objects (`QDate`, `QDateTime`, `QTime`), null variants (`QVariant.Null`, `NULL`), and Python `datetime.date`/`datetime.datetime` instances across feature extraction in `_run_cleaning_pipeline`, `clean_yield_data` Processing algorithm, manifest generators, and HTML review report serializers, ensuring cleaning completes without serialization errors on datasets containing dates/timestamps.

## 0.9.21 - 2026-08-17

### Fixed

- **`QgsMapCanvas.panAction()` Type Error in Vertex Editing Tool**: Fixed `canvasPressEvent` and `canvasMoveEvent` to pass the `QMouseEvent` / `QgsMapMouseEvent` directly rather than `QPoint`, preventing runtime `TypeError` when clicking or panning canvas during boundary vertex editing.
- **Adaptive Screen-Geometry Sizing**: Replaced hardcoded dialog sizing with dynamic available geometry detection (90% width / 88% height scaling), ensuring the dialog fits all desktop and laptop screens (including 1366x768 and high-DPI scaling) without overflowing or cutting off bottom buttons.
- **Responsive Scroll Area Wrappers**: Wrapped all 4 workflow tabs in frameless, resizable `QScrollArea` containers so all panels and controls are accessible on smaller screens.
- **Reduced Canvas Minimum Heights**: Set canvas minimum heights to `240` (with flexible vertical layout stretch) so embedded maps scale gracefully across all screen sizes.

### Added

- **Automatic Live Styling & Default Legend on Tab 3 (Prepare Dataset)**: Removed the manual "Apply Styling" button; the preview map now immediately applies styling and displays the live classification legend by default as soon as the dataset is prepared, and dynamically re-styles on attribute/ramp change.
- **Full Original Column Selection on Tab 3 Preview**: Dynamically populated the `Display Attribute` dropdown on Tab 3 with all original dataset columns (`prepared_layer.fields()`) alongside canonical attributes, enabling immediate inspection of raw sensor columns.

## 0.9.20 - 2026-08-17

### Added

- **Full Original Dataset Attributes in HTML Review**: Discovered and embedded every raw source attribute from the input file into the HTML review web app dropdowns (`Original Dataset Attributes` group) and rich popup inspector, enabling visualization and graduated styling for all raw sensor attributes (e.g. `Yld_Vol_Dr`, `Yld_Mass_D`, `Crop_Flw_M`, `Speed_mph_`, `Swth_Wdth_`, `Pass_Num`, `Elevation`).
- **Boundary-Clipped Interpolated Yield Grid Surface**: Integrated in-memory IDW (Inverse Distance Weighting) continuous surface generation clipped strictly to the field boundary polygon; added as a selectable layer (`Cleaned Yield Interpolated Surface (Grid)`) in the HTML review web app.
- **Configurable Grid Size on Tab 4 (Clean & Review)**: Added user-configurable `HTML Surface Grid` setting (default `30.0 ft` in imperial, `10.0 m` in metric) on the Clean & Review tab that flows directly into the HTML review surface raster generator.
- **Streamlined 3-Basemap Selection with Enhanced Road Network**: Refined basemaps in the HTML review app to `Hybrid`, `Satellite`, and `Streets`, with `Hybrid` combining high-resolution satellite imagery, Esri World Transportation road networks, and geographic labels for maximum spatial context.

### Fixed

- **Swipe Compare Slider Smooth Dragging**: Fixed slider drag event propagation and disabled map panning during slider movement (`map.dragging.disable()`), allowing the swipe comparison divider to glide smoothly without panning the underlying map canvas.
- **Accurate Physical Field Acreage Calculation**: Replaced placeholder observation multipliers with true physical harvested area summation $\sum (\text{speed} \times \Delta t \times \text{swath\_width})$ and exact boundary polygon metrics, producing accurate field acreage.
- **Zoom Control UI Overlap**: Relocated Leaflet zoom buttons away from the top-left `#mapOptionsCard` panel to eliminate control overlap.

## 0.9.19 - 2026-08-17

### Added

- **Embedded Interactive Map Canvas on Clean & Review (Tab 4)**: Added a full-featured, embedded `QgsMapCanvas` directly within the Clean & Review tab (in the lower workspace area), rendering cleaned and excluded observations with dynamic styling without cluttering or polluting the main QGIS project canvas.
- **In-Modal Interactive Point Selection & Cleanup Tools**: Added `🔲 Select Points (Drag Box)` tool enabling users to drag selection rectangles or click points directly on the embedded Clean & Review canvas.
- **Direct In-Modal Manual Exclusion & Restoration**: Added `❌ Exclude Selected (Delete)`, `♻️ Restore Selected (Un-delete)`, and `↶ Clear All Deletions` buttons that immediately update point clean status, recompute Clean vs. Raw statistics, refresh live excluded filter counts, and update map canvas symbology instantaneously.
- **Live Classification Legend Bar on Clean Map Canvas**: Integrated graduated and categorized legend chips below the map canvas showing active range boundaries and unit labels for all attributes (Dry Yield, Exclusion Status, Wet Yield, Moisture, Speed, Swath Width).
- **Embedded Map Navigation & Scale Bar**: Included Pan, Zoom In, Zoom Out, and Zoom Full controls alongside a live Scale, Display Units, and CRS indicator on Tab 4.

## 0.9.18 - 2026-08-17

### Added

- **Calculation Precedence with Automated Direct Fallback**: Established primary execution precedence for dynamic yield calculation whenever physical sensor variables (mass flow wet, ground speed, swath width, and moisture) are present; direct dry yield attributes (`Yld_Vol_Dr`) automatically serve as a seamless fallback whenever sensor flow is zero or missing.
- **Value-Range Distribution Intelligence for Column Mapping**: Added distribution analysis in `detect_columns` that evaluates sample median values against typical agronomic crop ranges ($15 - 450\text{ bu/ac}$), ensuring volumetric dry yield columns (`Yld_Vol_Dr`) are correctly recognized and chosen over raw mass-per-area rates (`Yld_Mass_D`).
- **Live Step-by-Step Sample Yield Calculation in Advisory**: Embedded a fully worked-out step-by-step sample calculation directly in the **📊 Yield Calculation & Data Advisory** box using representative data from the active file, detailing Mass Flow (lb/s &rarr; kg/s), Ground Speed (mph &rarr; m/s), Swath Width (ft &rarr; m), Area Harvest Rate ($m^2/s$ and ac/hr), Wet Yield ($kg/ha$), Market Moisture Adjustment, and final Dry Yield ($bu/ac$ and $kg/ha$) with comparison against direct columns.
- **Volume vs. Mass Mapping Clarification**: Updated mapping table canonical field labels to `Dry Yield (bu/ac Volumetric / kg/ha)` and unit options to explicitly differentiate `bu/ac (Volume)` from `kg/ha (Mass)` and `lb/ac (Mass)`.

## 0.9.17 - 2026-08-17

### Added

- **Live Classification Legend Bar on Prepare Dataset Preview Map (Tab 3)**: Embedded dynamic color ramp classification legend chips with active ranges and unit labels (e.g. `165.0 – 195.0 bu/ac`) matching the active graduated renderer.
- **50% Initial Default Boundary Vertices & ±15% Progression (Tab 2)**: Removed the step spinbox control; boundaries now automatically load with a clean 50% vertex default, and clicking `✨ Smooth / Simplify (-15%)` or `➕ Densify / Add Vertices (+15%)` removes or adds exactly 15% of vertices per click with live percentage and delta count feedback.
- **Yield Calculation & Data Advisory Audit (Tab 1)**: Added automatic yield data detection with clear user advisory explaining whether direct dry yield (`Yld_Vol_Dr`) or flow-based derivation (`Crop_Flw_M`, `Speed_mph_`, `Swth_Wdth_`, `Moisture__`) is utilized, along with instructions on how to adjust mappings.
- **Smart Flow-Based Dry Yield Derivation Fallback**: Implemented automatic calculation of canonical dry yield from mass flow, ground speed, swath width, and grain moisture when a direct dry yield column is missing or unmapped.

### Fixed

- **Column Alias Prioritization**: Prioritized volumetric dry yield columns (`Yld_Vol_Dr`, `dry_yield`, `yield_dry`, `dry_bu_ac`) before mass-per-area (`Yld_Mass_D`) so bu/ac yield columns are mapped by default.

## 0.9.16 - 2026-08-17

### Fixed

- **Raw Pounds/Acre Yield Handling**: Resolved issue where files with yield recorded in pounds per acre (`lb/ac`, e.g. ~11,000 lb/ac) were treated as raw bushels per acre and filtered out completely by the Maximum Yield threshold (`> 398 bu/ac`). Added `pounds_per_acre_to_kg_per_hectare` and `kg_per_hectare_to_pounds_per_acre` conversions, wired `_reviewed_source_units` directly to canonical audit generation, and added smart auto-detection for yield values exceeding 450.

### Added

- **10-Step Boundary Smoothing & Densification Progression**: Added 10-step progression (defaulting to step 5) on the boundary toolbar that advances step intensity with each click while updating live vertex delta counts.
- **Scale and Units Display on Prepare Dataset Map Preview**: Added live `📏 Scale: 1:N • Display Units • CRS` indicator below the Prepare Dataset map canvas that updates dynamically on pan and zoom.

## 0.9.15 - 2026-08-17

### Fixed

- **Remove Interior Holes**: Fixed `fill_polygon_holes` by reconstructing the geometry directly from its exterior boundary rings, ensuring that all internal voids, holes, and slivers are completely and cleanly eliminated on both single and multi-polygon geometries.
- **Prepare Dataset Execution**: Fixed missing `prepare_status` reference in `_run_prepare_dataset` that prevented dataset creation from completing.
- **Seamless Panning during Vertex Editing**: Integrated direct canvas panning (left-click drag on empty canvas, middle click, or right-click drag) inside `ModalBoundaryVertexTool` so panning never disables or untoggles vertex editing.

### Added

- **Multi-Step Intensity Control for Smooth & Densify (Tab 2)**: Added a dedicated `Step: [ 1 ]` spinbox multiplier on the boundary toolbar and a live vertex feedback label (`Vertices: N (+/- Δ)`) so users can apply multiple smoothing/densification steps in custom increments with each click.

## 0.9.14 - 2026-08-17

### Fixed

- **Graduated Color Ramp Symbology**: Fixed renderer so every range category explicitly receives interpolated colors from the chosen color ramp (Red-Yellow-Green, Viridis, Blues, Plasma, Spectral, Magma) rather than default grey markers.
- **Field Boundary Canvas Panning**: Fixed canvas panning tool assignment on Tab 2 so users can pan smoothly around the boundary.
- **Prepare Dataset Layout Spacing**: Pinned **Dataset name and output** at the top of Tab 3 and removed empty whitespace before running.

### Added

- **Prepare Dataset Map Navigation**: Added integrated **`✋ Pan`**, **`🔍+`**, **`🔍-`**, and **`📐 Zoom Full`** buttons to the Step 3 observations preview canvas.
- **Progressive Step Geometry Tools (Tab 2)**:
  - **`✨ Smooth / Simplify (Step)`**: Gently simplifies boundary geometry by a subtle ~5% per click to avoid extreme collapsing.
  - **`➕ Densify / Add Vertices (Step)`**: Subdivides boundary segments to add intermediate vertices and increase resolution.

## 0.9.13 - 2026-08-17

### Fixed

- **`QgsGeometry` Import Error**: Resolved `name 'QgsGeometry' is not defined` by importing `QgsGeometry` and `QgsPointXY` in the inspection dialog.
- **Tab 2 Layout Docking**: Ensured the **Boundary setup** groupbox stays pinned at the very top of Tab 2 without empty blank spacing.

### Added

- **Per-Field Unit / Format Pulldowns (Tab 1)**:
  - Added a dedicated **Unit / Format** dropdown column in the **Review mapping** table tailored to each canonical field (e.g. `bu/ac`, `kg/ha`, `tonne/ha`, `lb/ac` for yield; `%`, `fraction` for moisture; `ft`, `in`, `m`, `rows (30 in)` for swath; `mph`, `km/h`, `m/s` for speed).
- **Representative Data Sample Extraction**:
  - Sample values now draw evenly from across the whole dataset (e.g. 10th, 35th, 65th, 90th percentiles + overall range) rather than just the first few header rows.
  - Formatted cleanly with typical values and `(range: min – max)` to provide realistic representation of the dataset.

## 0.9.12 - 2026-08-17

### Added

- **Interactive In-Modal Vertex Editing (Tab 2)**:
  - Added dedicated in-modal vertex editor tool directly on the preview map canvas.
  - Users can click and drag vertices to reposition them, click on any boundary segment to add a vertex, and right-click on a vertex to delete it without leaving the dialog modal.
  - Added integrated canvas navigation controls: **Pan**, **Zoom In**, **Zoom Out**, and **Zoom Full**.
- **Expanded Boundary Map Group Layout**:
  - Expanded the boundary preview canvas to occupy full vertical space (`minimumHeight: 380` with stretch layout).

### Removed

- Removed the redundant "Boundary not imported / created" text box on Tab 2.

## 0.9.11 - 2026-08-17

### Added

- **Live Data Sample Values in Column Mapping (Tab 1)**:
  - Top inspection results table now displays an `Example values from data` column showing actual formatted values from inspected features.
  - Review Mapping table now includes a dedicated `Sample values from file` column that live-updates whenever any column dropdown is changed.
- **Boundary Geometry Cleanup & Editing Tools (Tab 2)**:
  - **`🧹 Remove Interior Holes`**: Removes all internal sliver rings and interior holes from the polygon boundary with one click.
  - **`✨ Smooth / Simplify`**: Simplifies boundary contours to remove jagged artifacts and reduce excess vertex density.
  - **`✏️ Modify in QGIS (Vertex Tool)`**: Activates the layer in QGIS, enables editing mode, and triggers the native Vertex Tool for interactive vertex addition, repositioning, and deletion.
  - **`↶ Reset Original`**: Restores the boundary geometry to the initial imported/derived geometry.

## 0.9.10 - 2026-08-17

### Added

- **Two-Step Field Boundary Workflow (Tab 2)**:
  - Added **`Import / Create Boundary`** primary action button (starts RED as required action).
  - Added a live embedded **`Field Boundary Preview`** `QgsMapCanvas` in the lower preview area.
  - Clicking `Import / Create Boundary` renders the imported or derived operational boundary polygon and zooms to its extent.
  - Added **`Continue to Prepare Dataset`** action button at the bottom of the tab, which becomes enabled and RED once the boundary is previewed, transitioning to GREEN upon advancing to Tab 3.

## 0.9.9 - 2026-08-17

### Added

- **Attribute & Color Ramp Controls on Step 3 Map Preview**:
  - Added an interactive **Display Attribute** selector dropdown (`Dry Yield (Default)`, `Wet Yield`, `Moisture (%)`, `Speed / Velocity`, `Swath Width`, `Elevation`, `Pass ID`).
  - Added an interactive **Color Ramp** dropdown (`Red-Yellow-Green (Standard)`, `Viridis`, `Blues`, `Plasma`, `Spectral`, `Magma`).
  - Re-styles the points on the embedded preview and triggers live repainting upon dropdown selection or clicking `Apply Styling`.

### Changed

- **Clean Points Preview (No Boundary Overlay)**:
  - Removed the solid field boundary polygon from the Step 3 preview canvas so only the graduated yield points are visible.

## 0.9.8 - 2026-08-17

### Added

- **Embedded Map Preview Canvas on Step 3**:
  - Integrated a live `QgsMapCanvas` directly inside Tab 3 (`Prepare Dataset`) below the summary card.
  - Automatically loads the prepared yield layer and field boundary with the graduated yield color ramp and zooms to extent.
- **Strict Workflow Action Button Progression**:
  - `Continue to Field Boundary` remains RED (action required) after inspection until clicked.
  - `Continue to Clean & Review` remains RED after dataset preparation until clicked.

### Fixed

- **Math Module NameError**:
  - Fixed missing `import math` in `inspection_dialog.py` that caused `Cleaning failed: name 'math' is not defined`.
- **Geographic Coordinate Projection for Spatial Filters**:
  - Added meter coordinate projection in `overlap.py` and `local_outlier.py` when observations are in geographic WGS84 coordinates ($^\circ$), preventing over-exclusion.
- **Pass Start/End Trimming Protection**:
  - Protected short passes from being 100% trimmed in `pass_edge.py`.
- **Pass ID Fallback**:
  - Automatically defaulted `pass_id` to `source_pass_id` in `canonicalizer.py` when present.

## 0.9.7 - 2026-08-17

### Added

- **Red-to-Green Stateful Workflow Action Buttons**:
  - `Inspect input` starts RED (`#dc2626`) and turns GREEN (`#16a34a`, `✓ Input Inspected & Columns Mapped`) upon completion.
  - `Continue to Field Boundary` transitions from RED to GREEN when columns are mapped.
  - `Confirm boundary and continue` transitions to GREEN (`✓ Boundary Confirmed - Continue`).
  - `Create prepared yield dataset` starts RED and transitions to GREEN (`✓ Prepared Yield Dataset Created`).
  - `Continue to Clean & Review` transitions to GREEN when dataset is ready.
  - `Execute Cleaning Pipeline / Apply Filters` starts RED and transitions to GREEN (`✓ Cleaning Completed / Filters Applied`).
- **Interactive Selected Points Map Canvas Inspector & Modal Editing Table**:
  - Integrated a live `QTableWidget` in Tab 4 connected to QGIS map canvas selections (`selectionChanged`).
  - Displays selected points attributes: `Point ID`, `Yield`, `Moisture %`, `Speed`, `Swath`, `Pass ID`, `Status`, and `Filter Reasons`.
  - Added in-modal manual override actions: `Select Points on Map Canvas`, `Exclude Selected (Manual Delete)`, `Restore Selected (Un-delete)`, `Apply Table Edits to Points`, and `Clear All Manual Deletions`.
- **Automated Graduated Yield Symbology on Step 3**:
  - Immediately applies graduated Red &rarr; Yellow &rarr; Green yield color ramp to the canvas upon dataset preparation and zooms map canvas to layer extent.
  - Displays a visual color ramp legend preview in the dataset creation status card.
- **Destination Folder Validation & Highlights**:
  - Renamed `Save inside` to `<span style='color: #dc2626; font-weight: bold;'>*</span> Destination / Output folder:` with dynamic red border validation when empty and green border when set.

## 0.9.6 - 2026-08-17

### Added

- **Full-Screen Leaflet Review Web Application**:
  - Rebuilt the HTML review report into a standalone, offline-ready GIS application matching the Fake Farm Data Review layout.
  - **Top Banner**: Added dark red header banner (`YIELD DATA CLEANER - AUDIT & CLEANING REVIEW`).
  - **Map Options Panel**: Basemap switcher (`Hybrid`, `Satellite (Esri)`, `OpenStreetMap`, `Streets`, `Topographic`, `CartoDB Positron`, `CartoDB Dark`), Data Opacity slider (0–100%) with live percentage display, Field selector, and Reset Extent button.
  - **KPI Summary Card**: 2-column metrics card displaying Fields in run, Estimated Field Area, Clean Points, Excluded Points (% Filtered), Mean Clean Yield, and Mean Raw Yield, with collapsible toggle.
  - **Side-by-Side Swipe Comparison Mode**: Center slider handle (`( <-> )`) that allows interactive swipe comparison between any two layers or attributes with smooth overlay clipping.
  - **Left & Right Layer Control Cards**: Independent selectors for Layer (`Cleaned Yield`, `Raw Observations`, `Excluded Points`), Attribute (`Dry Yield`, `Moisture`, `Speed`, `Swath Width`, `Clean Status`), and Color Ramp (`Red-Yellow-Green`, `Viridis`, `Blues`, `Spectral`, `Categorized Status`) with interactive graduated color bars.
  - **Point Tooltips & Popups**: Rich feature popups displaying Observation ID, Clean Status, Exclusion Reason codes, Yield, Moisture, Speed, Swath Width, and Pass ID.

### Fixed

- **Yield Filter Attribute Resolution**:
  - Fixed issue where observations with `yield_dry_mass_area`, `dry_yield_mass_area`, `yield`, or `dry_yield` were ignored or misclassified in `ranges.py`, `quality.py`, `local_outlier.py`, and `inspection_dialog.py`.
- **Optional Header Engagement Check**:
  - Changed `Header Down Req` filter checkbox to default to `False` (optional) so datasets with unrecorded or inverted header sensors do not exclude 100% of points.
- **Pass Reconstruction Propagation**:
  - Properly attached reconstructed `pass_id` and `heading_deg` updates to observations prior to running cleaning filters.
- **Modeless Map Selection Interaction**:
  - Updated `YieldInputInspectionDialog` to run modelessly (`show()`, `raise_()`, `activateWindow()`) and configured `_select_on_map` to set the active layer and trigger map canvas selection without being blocked by modal loops.

## 0.9.5 - 2026-08-17

### Added

- **USDA-ARS Yield Editor Interactive Layout in Tab 4**:
  - Structured filter selection grid with individual checkboxes, parameter spinboxes, and **live excluded / deleted point counts** per filter stage.
  - **Yield Statistics Table (Clean vs Raw)**: Dynamically computes and displays Mean Yield, Standard Deviation (STD), Coefficient of Variation (CV%), Observations Count (N & % Excluded), and Yield Range with real-time differences.
  - **Interactive Display Symbology Presets (USDA Legend)**: 1-click radio presets for `Yield` (Quantile ramp), `Moisture` (Blues ramp), `Velocity` (Viridis ramp), `Swath Width` (Spectral ramp), and `Exclusion Status` (Green accepted / Red excluded points).
  - **Map Selection & Manual Override Tools**: Interactive tools to `Select Points on Map Canvas`, `Exclude Selected (Manual Delete)`, `Restore Selected (Un-delete)`, and `Clear All Manual Deletions`.
- **Default Crop Test Weights & Standard Moisture**:
  - Expanded `crop_profiles.py` with standard reference bushel test weights and market moisture baselines across Corn (56 lb/bu @ 15.5%), Soybean (60 lb/bu @ 13%), Wheat (60 lb/bu @ 13.5%), Barley (48 lb/bu @ 14.5%), Oats (32 lb/bu @ 14%), Sorghum (56 lb/bu @ 14%), Canola (50 lb/bu @ 10%), and Sunflower (28 lb/bu @ 10%).
  - Added user-customizable spinboxes for test weight and standard moisture on Tab 1 (`Input & Mapping`) and Tab 4 (`Clean & Review`).

## 0.9.4 - 2026-08-17

### Fixed

- Fixed `AttributeError: 'CleaningRecipe' object has no attribute 'pass_edge_start_trim_s'` when preparing datasets and resetting recipe defaults.
- Added comprehensive compatibility properties to `CleaningRecipe` (`pass_edge_start_trim_s`, `pass_edge_end_trim_s`, `speed_min_m_s`, `speed_max_m_s`, `yield_min_dry_mass_area`, `yield_max_dry_mass_area`, `overlap_filter_enabled`, `spatial_outlier_enabled`, `spatial_outlier_radius_m`, `spatial_outlier_stds`).
- Aligned UI recipe collectors and default initializers to canonical recipe attributes.

## 0.9.3 - 2026-08-17

### Added

- Added animated progress bar, button text feedback ("Creating prepared dataset... Please wait..."), system wait cursor, and live status updates when clicking **Create prepared yield dataset**.
- Added corresponding progress feedback and wait state handling for **Inspect input** and **Execute Cleaning Pipeline**.

## 0.9.2 - 2026-08-17

### Fixed

- Fixed `ImportError` on speed unit conversions (`mph_to_m_per_s`, `m_per_s_to_mph`) by defining canonical aliases in `units.py`.
- Fixed test weight parameter passing in `bushels_per_acre_to_kg_per_hectare` within the guided cleaning tab.
- Added automated dynamic module import test suite verifying all packaged modules import cleanly without unresolved symbols.

## 0.9.1 - 2026-08-17

### Fixed

- Fixed `ImportError` on plugin startup by resolving the `reconstruct_passes` import symbol in `inspection_dialog.py` and maintaining backwards compatibility.

## 0.9.0 - 2026-08-17

### Added

- **Integrated Tab 4 (Clean & Review)**: Added full cleaning recipe configuration directly inside the Guided Workflow dialog.
- **1-Click Full Cleaning Pipeline**: Executes pass reconstruction, sensor delay shifting, motion limits, swath trimming, swath overlap, crop yield/moisture ranges, and robust local spatial outlier detection in one step.
- **Direct HTML Review Launcher**: Added `Open HTML Review Report` button launching standalone interactive review maps and KPI charts in the user's default browser.
- **QGIS Map Layer Additions**: Automatically loads `accepted_observations` and `excluded_observations` into the active QGIS project map canvas.
- **ADAPT Standard Export Action**: Added direct 1-click export of cleaned yield operations to AgGateway ADAPT Standard format from the UI.

## 0.8.1 - 2026-08-17

### Added

- Prominent red action button styling (`#inspectInputButton`, `#continueToBoundaryButton`, `#confirmFieldBoundaryButton`, `#createPreparedDatasetButton`) to guide users through each workflow step.
- Timestamped run folders (`<field>_<crop>_<date>_<time>`) preventing filename collision on repeated executions.

### Fixed

- Resolved OGR `Creation of field duration_s failed (Cannot create field duration_s. A field with the same name already exists)` error by making canonical field collision detection strictly case-insensitive.

## 0.8.0 - 2026-08-17

### Added

- AgGateway ADAPT Standard data-only export and import package support (`adapt_manifest.json`, `context.json`, `logged_data.json`, `spatial_coverage.geojson`).
- Harvest swath coverage polygon generator (`coverage_builder.py`) creating oriented rectangular footprints.
- Built-in vendor presets and header signature detection for Ag Leader and John Deere / GreenStar text exports.
- `export_adapt` Processing algorithm registered in provider.

## 0.7.0 - 2026-08-17

### Added

- Standalone, portable before/after HTML cleaning review report with offline Canvas spatial visualizer, KPI cards, and filter breakdown table.
- Complete run package writer generating manifest JSON, recipe JSON, mapping JSON, filter summary CSV, and run log.
- Cleaned CSV export helper retaining original and canonical attributes.
- Added `REVIEW_HTML` output parameter to `CleanYieldDataAlgorithm`.

## 0.6.0 - 2026-08-17

### Added

- Sensor flow and moisture delay chronological pass shifting and automated cross-pass variance delay estimation.
- Swath and coverage overlap detection filter using 2D spatial grid indexing.
- Robust local spatial yield outlier filter using neighborhood Median and Median Absolute Deviation (MAD).
- Full audit integration for manual point exclusion (`manual_exclude`) and restoration (`manual_restore`).
- Extended `CleaningRecipe` model with delay, overlap, and local spatial outlier parameters.

## 0.4.0 - 2026-08-17

### Added

- Core deterministic cleaning filter suite (quality, header state, min/max/change speed, swath width, pass-edge start/end latency, crop-aware yield and moisture ranges).
- Automated statistical recommendation engine generating threshold suggestions with percentiles, evidence, and simulated impact.
- `CleaningRecipe` serialization model supporting versioned JSON recipe configurations and default crop presets.
- `CleanYieldDataAlgorithm` registered in the QGIS Processing provider.
- Full test coverage across individual filter rules, combined cleaning pipelines, recommendation distributions, and recipes.

## 0.3.0 - 2026-08-17

### Added

- Multi-factor harvest pass reconstruction engine using turn detection, time gaps, distance jumps, and header state transitions.
- LineString harvest pass vector generator with duration, length, heading, point count, and confidence attributes.
- User/monitor-supplied source pass validation with continuity and coherence scoring.
- `ReconstructPassesAlgorithm` registered in the QGIS Processing provider.
- Comprehensive pure-Python unit test coverage for straight passes, turns, stops, jumps, header lifts, multiple combine machines, and heading estimation.

## 0.1.0 - 2026-08-12

### Added

- Initial public QGIS plugin and Processing-provider foundation.
- Guided input-inspection dialog for a loaded QGIS layer or local file.
- Editable mapping review with reusable, bounded JSON mapping profiles.
- Canonical yield-observation schema and stable field definitions.
- Corn, soybean, and wheat crop/unit conversion profiles.
- Column-name recognition with confidence and explanations.
- Canonical audit-layer Processing algorithm that preserves source values.
- CRS recognition, confirmation, automatic local UTM selection, transformation, and provenance.
- Generic delimited-text inspection.
- Existing-boundary validation and swath-width/concave-hull operational boundary
  derivation with confidence and provenance.
- Non-destructive inside/outside boundary classification outputs.
- Pure-Python and installed-QGIS tests, packaging, archive validation, version checks,
  and QGIS-aligned security scans.
- Product specification covering phased delivery through 1.0 and future equipment-platform connectors.
- Unified guided workflow with top-level Input & Mapping, Field Boundary, and
  Prepare Dataset tabs, embedded execution, and contextual right-side help.
- Added a guided final run that writes both the prepared observations and boundary,
  uses field/crop/date output names, and increments repeated run folders instead of
  blocking on existing or partial output files.
- Added the Yield Data Cleaner for QGIS logo as the packaged plugin and toolbar icon.
