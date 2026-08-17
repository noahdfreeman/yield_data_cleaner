# User Guide: Interactive 4-Tab Workflow

The Yield Data Cleaner interactive workflow is organized into four sequential, guided tabs designed to take you from raw, uncleaned monitor files to an auditable, high-quality yield surface and dataset.

---

## Tab 1: Input & Column Mapping

The first tab handles data ingestion, automatic field identification, unit configuration, and coordinate reference system (CRS) verification.

### 1. Source Data Selection
- **Select QGIS Layer**: Pick an already loaded point or vector layer directly from the QGIS Layers panel.
- **Browse from File**: Click **Browse...** to import Shapefiles (`.shp`), GeoPackages (`.gpkg`), GeoJSON (`.geojson`), or Delimited CSV/TXT files from your computer.

### 2. Crop & Unit Selection
- Choose your crop (e.g., **Corn**, **Soybean**, **Wheat**, **Barley**, **Oats**, **Sorghum**, **Canola**, **Sunflower**).
- The standard market moisture and bushel test weight will be loaded automatically according to crop agronomic standards.
- Select your preferred working unit system: **Imperial** (bu/ac, mph, ft, lb) or **Metric** (t/ha, kg/ha, km/h, m, kg).

### 3. Column Mapping & Precedence Logic
The tool automatically scans attributes and assigns likely matches using statistical range analysis and column header heuristics.
- **Physical Sensor Calculation Precedence**: If raw mass flow, swath width, distance/speed, and moisture are present, the plugin will prioritize calculating the actual volumetric dry yield.
- **Direct Volumetric Yield Fallback**: If physical sensor parameters are missing or incomplete, the plugin automatically detects and falls back to existing dry yield columns (e.g., `Yld_Vol_Dr`, `DryYield`, `YIELD_BUAC`).
- **Data & Calculation Advisory**: Review the live calculation card at the bottom of the tab to see a step-by-step audit showing the exact math and representative quantile sample values from your dataset.

---

## Tab 2: Boundary & Pass Reconstruction

A clean field boundary and structured harvest passes are essential for eliminating false edge artifacts and detecting swath overlaps.

### 1. Field Boundary Setup
- **Select Existing Boundary**: Choose a polygon layer from QGIS or browse to an external boundary file.
- **Derive from Yield Data**: Click **Derive Boundary** to automatically calculate a tight boundary from combine swath footprints and point extents.
  - **Vertex Smoothing & Densification**: Default starts at 50% vertex count. Click **Smooth / Simplify** to remove 15% of vertices per click, or **Densify / Add** to add 15% more detail.
  - **Interactive Editing**: Click **Edit Boundary in Canvas** to manually move or delete vertices directly on the preview map with integrated panning.

### 2. Harvest Pass Reconstruction
- Combine monitor timestamps, heading changes, speed jumps, and distance gaps are evaluated to group continuous harvest swaths into discrete passes.
- Preview passes on the map color-coded by pass identifier.

---

## Tab 3: Filter & Parameter Adjustment

Configure the 8 core agronomic cleaning filter stages. You can accept the tool's automatically recommended thresholds or customize them.

### Filter Stages
1. **Flow & Moisture Delays**: Calibrate sensor transit delays from header cut to sensor plate.
2. **Speed Limits & Rapid Acceleration**: Remove points where the combine is stopped, turning too fast, or experiencing GNSS position jumps.
3. **Swath Width & Truncated Swaths**: Filter out zero or abnormal header cuts.
4. **Pass-Edge & Start/End Trimming**: Remove ramping-up and ramping-down flow errors at the beginnings and ends of passes.
5. **Yield & Moisture Range**: Exclude values outside biological limits (e.g. negative or 800+ bu/ac).
6. **Swath Overlap Detection**: Detect when the combine header overlaps previously harvested terrain.
7. **Local Spatial Outlier Detection**: Flag points that deviate significantly from their immediate neighbors using spatial moving-window statistics.

---

## Tab 4: Clean & Review Canvas

Tab 4 provides an in-modal inspection environment to review the filtered results and perform manual data curation.

### 1. Interactive Selection & Manual Exclusions
- **Select Box**: Draw a box on the canvas to select points.
- **Exclude Selected (Delete)**: Mark selected points as excluded. Excluded points disappear from the cleaned yield map instantly and are tracked in the statistical summary.
- **Restore Excluded (Un-delete)**: Restore mistakenly excluded points back to accepted status.

### 2. Statistical Comparison Table
Review the 4-column KPI comparison:
- **Cleaned Dataset** vs. **Raw / Source Data** vs. **Difference / Excluded**
- Measures: **Mean Yield**, **Standard Deviation (STD)**, **Coefficient of Variation (CV %)**, **Observations (N)**, and **Yield Range**.

### 3. Final Export Actions
- **Open Run Folder**: Access GeoPackages, CSVs, recipes, and manifests.
- **Open HTML Review**: Launch the full-screen interactive Leaflet review web app in your browser.
- **Export ADAPT Package**: Export the cleaned dataset and coverage geometry into AgGateway ADAPT Standard JSON and GeoParquet.

---

## Standalone Leaflet HTML Data Review

The generated HTML review is a self-contained, portable single-file web app that runs in any web browser without server setup.

- **3 High-Definition Basemaps**: Esri Hybrid (with prominent transportation roads), Satellite, and Streets.
- **Swipe Comparison Slider**: Compare Cleaned vs. Raw or Interpolated Surface vs. Points with a smooth swipe handle that doesn't pan the map.
- **Interpolated Surface (IDW Grid)**: View a continuous yield map clipped strictly to the field boundary with customizable cell size (e.g., 30 ft).
- **Expandable Distribution & Classification Drawer**:
  - View real-time 18-bin SVG frequency histograms colored by your active color ramp.
  - Switch classification modes dynamically: **Quantile (Equal Count)**, **Equal Interval**, **Natural Breaks (1D k-means / Jenks)**, and **Standard Deviation**.
  - Adjust class count from 3 to 8 bins.
- **Rich Feature Inspection**: Click any observation point to view its cleaning status, exclusion reasons, yield, moisture, speed, swath width, and all original vendor attributes.
