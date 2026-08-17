# Yield Data Cleaner

Yield Data Cleaner is an experimental, open-source QGIS plugin for reviewing and
cleaning combine yield-monitor data one field at a time. It is inspired by the
filtering concepts in USDA-ARS Yield Editor 2 and is being implemented as a new,
auditable Python/PyQGIS workflow.

Development is currently at version `1.0.0`. Milestones provide the
plugin foundation, editable automatic column suggestions with agronomic value-range distribution scoring and priority for volumetric dry yield (Yld_Vol_Dr), primary physical sensor calculation precedence with direct dry yield fallback, per-field unit/format dropdown selectors with clear volume vs mass differentiation and lb/ac support, representative quantile sample values in column mapping, live step-by-step Yield Calculation & Data Advisory audits, reusable mappings,
crop/unit profiles, CRS recognition/transformation, field boundary derivation/classification,
two-step boundary import/creation with top-docked setup, live boundary preview, exterior-ring hole removal, 50% initial vertex default with interactive ±15% simplification and densification (add vertices), in-modal interactive vertex editing with integrated canvas panning,
harvest pass reconstruction with turn and gap detection, non-destructive cleaning filter stages
(sensor delays, motion, swath, pass-edge, overlap, ranges, local spatial outliers), statistical recommendations,
an integrated 4-tab guided workflow dialog with USDA Yield Editor-style interactive filtering, parameter adjustment re-execution, red-to-green action buttons,
embedded map canvas previews with live classification legends, live scale bar/units, attribute and color ramp controls, pan/zoom tools across all preview canvases,
in-modal Clean & Review interactive map canvas with box point selection, manual exclusion (delete) and restoration (un-delete) without polluting QGIS project layers, destination folder validation, live excluded point counts,
Clean vs Raw statistics comparison, a full-screen Leaflet review web app with 3 basemaps (Hybrid with prominent transportation roads, Satellite, Streets), boundary-clipped IDW interpolated yield grid surface with configurable cell size, toggleable field boundary polygon layer, full 4-column statistical audit table, expandable variable distribution frequency histogram, interactive classification mode (Quantile, Equal Interval, Natural Breaks, Std Dev) and class count adjusters, full original attribute styling/inspection, non-panning swipe compare slider, adaptive dialog screen sizing with scroll containers, and AgGateway ADAPT Standard / vendor interoperability.

## Planned workflow

1. Select a point layer already loaded in QGIS or browse for a local file.
2. Review automatically suggested column mappings and source CRS.
3. Select, browse for, or configure derivation of one field boundary.
4. Choose a parent output folder and create the prepared dataset.
5. Reconstruct harvest passes and review recommended filters.
6. Apply non-destructive cleaning while retaining every source observation and reason.
7. Save a GeoPackage run package and portable HTML before/after review.

The guided window keeps Input & Mapping, Field Boundary, and Prepare Dataset as
top-level tabs. Context-sensitive instructions remain visible in a right-side
help panel. A run receives a collision-safe folder and filenames based on the
field or boundary name, crop, and date, such as
`Beard_BND_corn_2026-08-12/Beard_BND_corn_2026-08-12_yield_data.gpkg`.

See [YIELD_DATA_CLEANER_SPECIFICATION.md](YIELD_DATA_CLEANER_SPECIFICATION.md)
for the phased delivery plan and acceptance gates.

## Documentation

Detailed documentation is available in the [`docs/`](docs/index.md) directory:

- **[Documentation Hub](docs/index.md)**: Full guide directory.
- **[User Guide](docs/user_guide.md)**: Step-by-step interactive workflow tutorial.
- **[Column Mapping & Input Formats](docs/column_mapping.md)**: Attribute detection and vendor preset reference.
- **[Crop Profiles & Units](docs/crops_and_units.md)**: Crop moisture, test weights, and conversion mathematics.
- **[Filter Methodology](docs/filter_methodology.md)**: Agronomic cleaning logic and execution sequence.
- **[Field Boundary Derivation](docs/boundary_derivation.md)**: Swath footprint buffering and vertex editing.
- **[QGIS Processing Algorithms](docs/processing_algorithms.md)**: PyQGIS and Processing Toolbox reference.
- **[Output Schema & Reason Codes](docs/output_schema.md)**: GeoPackage structure and audit reason codes.
- **[AgGateway ADAPT Interoperability](docs/adapt_interoperability.md)**: ADAPT JSON and GeoParquet export guide.
- **[Scientific Validation Report](docs/validation_report.md)**: Benchmarks and verification methodology.
- **[Compatibility Report](docs/compatibility_report.md)**: Supported QGIS versions and OS matrix.
- **[Privacy & Data Security](docs/privacy_and_security.md)**: Local-first execution and privacy statement.

## Development

Run the pure-Python tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Build and validate an installable ZIP:

```powershell
python tools/package_qgis_plugin.py
python tools/validate_release_archive.py dist/yield_data_cleaner-0.9.4.zip
```

Run the same blocking security tools used by the QGIS Plugin Repository:

```powershell
python -m pip install -r requirements-dev.txt
bandit -r yield_data_cleaner -q
detect-secrets scan yield_data_cleaner
```

QGIS performs its own authoritative asynchronous scan after upload; a local
pass does not claim repository approval.

### Live QGIS development link

Link the source package into the default QGIS profile once:

```powershell
.\tools\install_development_link.ps1
```

The installed path is a Windows directory junction, so later source edits are
visible immediately. With QGIS Plugin Reloader installed, select
`yield_data_cleaner` and reload after each update. Restart QGIS when plugin
metadata or the package layout changes.

## Status and limitations

- Version `0.1.0` is experimental and is not approved for agronomic decisions.
- No source observation is silently deleted by the planned cleaning workflow.
- Derived boundaries are operational harvest extents requiring visual review;
  they are not labeled as legal or ownership boundaries.
- Proprietary USDA Yield Editor OCX components are not included.
- John Deere Operations Center and other equipment-platform connectors are post-1.0 roadmap items.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
