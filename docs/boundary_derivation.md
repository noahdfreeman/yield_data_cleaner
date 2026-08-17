# Field Boundary Derivation & Editing

A precise field boundary defines the scope of analysis, eliminates erroneous headland turn points recorded outside the field, and clips the final interpolated yield surface.

---

## Derivation Methods

Yield Data Cleaner supports three boundary acquisition workflows:

### 1. Existing Boundary Selection
Import a boundary polygon directly from an active QGIS layer or an external file (`.gpkg`, `.shp`, `.geojson`).

### 2. Automated Geometric Derivation
When no boundary file exists, Yield Data Cleaner calculates a polygon footprint from the harvest points:
- **Swath Footprint Buffering**: Buffers each harvest point by half its swath width along its travel direction to generate cutting polygons.
- **Dissolve & Concave Hull**: Merges individual footprints and runs an optimized concave hull algorithm to capture the perimeter.
- **Hole Removal**: Automatically removes internal donut holes and gaps between passes, ensuring a solid field polygon.

### 3. Interactive Vertex Editing
Edit or refine the boundary directly on the preview map:
- **Vertex Simplification & Densification**: Starts at a balanced 50% vertex count. Click **Smooth / Simplify** to drop 15% of vertices per click, or **Densify / Add** to increase contour detail.
- **In-Canvas Point Manipulation**: Drag vertices to adjust boundaries around tree lines, waterways, or fence rows.

---

## Boundary Clipping & Surface Interpolation

The field boundary serves two critical analytical functions:

1. **Point Filtering**: Any harvest point falling outside the boundary is tagged with the `OUTSIDE_BOUNDARY` reason code and excluded from the cleaned yield dataset.
2. **Surface Raster/Grid Clipping**: When generating the continuous inverse-distance weighted (IDW) yield grid, cells falling outside the boundary polygon are strictly masked to `null` to prevent artificial spatial extrapolation beyond field edges.
