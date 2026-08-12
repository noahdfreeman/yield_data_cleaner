# Changelog

All notable changes to Yield Data Cleaner will be documented here.

## 0.1.0 - Unreleased

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
