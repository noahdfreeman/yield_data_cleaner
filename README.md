# Yield Data Cleaner

Yield Data Cleaner is an experimental, open-source QGIS plugin for reviewing and
cleaning combine yield-monitor data one field at a time. It is inspired by the
filtering concepts in USDA-ARS Yield Editor 2 and is being implemented as a new,
auditable Python/PyQGIS workflow.

Development is currently at version `0.1.0`. The first milestone provides the
plugin foundation, editable automatic column suggestions, reusable mappings,
crop/unit profiles, CRS recognition/transformation, and a canonical audit-layer
output. The first Phase 2 slice can prepare an existing or derived operational
boundary and non-destructively classify inside/outside observations. Cleaning
filters and production claims remain experimental until they are validated with
representative raw monitor data.

## Planned workflow

1. Select a point layer already loaded in QGIS or browse for a local file.
2. Review automatically suggested column mappings and source CRS.
3. Select, browse for, digitize, or derive one field boundary.
4. Reconstruct harvest passes and review recommended filters.
5. Apply non-destructive cleaning while retaining every source observation and reason.
6. Save a GeoPackage run package and portable HTML before/after review.

See [YIELD_DATA_CLEANER_SPECIFICATION.md](YIELD_DATA_CLEANER_SPECIFICATION.md)
for the phased delivery plan and acceptance gates.

## Development

Run the pure-Python tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Build and validate an installable ZIP:

```powershell
python tools/package_qgis_plugin.py
python tools/validate_release_archive.py dist/yield_data_cleaner-0.1.0.zip
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
