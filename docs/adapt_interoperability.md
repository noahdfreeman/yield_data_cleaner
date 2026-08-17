# AgGateway ADAPT Interoperability

Yield Data Cleaner supports standard data exchange compliant with the **AgGateway ADAPT Standard** (Agricultural Data Application Programming Toolkit), enabling interoperability with modern Farm Management Information Systems (FMIS) without proprietary lock-in.

---

## ADAPT Standard Export Format

When you click **Export ADAPT Package** in Tab 4:

1. **`harvest_data.json`**: An AgGateway-compliant JSON manifest declaring:
   - Field identification, crop representation, and machine operation metadata.
   - Spatial bounds and coordinate reference system (WGS84 EPSG:4326).
   - Standardized unit descriptors (e.g. `bu/ac`, `%`, `mph`, `ft`).
   - Summary telemetry: total accepted observations, mean yield, total area, and cleaning provenance.
2. **`harvest_coverage.parquet` / GeoParquet**: Standard GeoParquet representation of accepted harvest point geometries and spatial coverage footprints.
3. **`recipe.json`**: Auditable record of every threshold and algorithm setting used in the cleaning run.

---

## Import Support

Yield Data Cleaner can ingest ADAPT Standard harvest packages:
- Reads ADAPT JSON context and linked spatial files.
- Automatically maps ADAPT spatial and crop attributes directly into canonical observation layers.
