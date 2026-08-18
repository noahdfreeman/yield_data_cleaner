# Yield Data Cleaner - Product and Implementation Specification

**Document status:** Initial development specification

**Last updated:** 2026-08-17

**Product name:** Yield Data Cleaner

**QGIS plugin ID:** `yield_data_cleaner`

**Public repository:** <https://github.com/noahdfreeman/yield_data_cleaner>

**Planned license:** GPL-3.0-or-later

**Current development version:** 1.0.1
**Target public release:** 1.0.1

## 1. Delivery status

The check boxes in this document are the delivery record. A checked item is a
decision or deliverable that has been completed and reviewed. An unchecked item
is planned or awaiting validation.

### Confirmed product decisions

- [x] Build a public, open-source QGIS plugin.
- [x] Use the name **Yield Data Cleaner**.
- [x] Use `yield_data_cleaner` as the plugin and Processing provider identifier.
- [x] Use <https://github.com/noahdfreeman/yield_data_cleaner> as the public repository.
- [x] Process one field per run in version 1.
- [x] Support corn, soybean, and wheat in version 1.
- [x] Default to Imperial units and support Metric input, display, and output conversions.
- [x] Provide both an interactive guided workflow and a QGIS Processing algorithm.
- [x] Detect and map source columns automatically, while requiring review of uncertain mappings.
- [x] Accept yield data from either a layer already loaded in QGIS or a file selected from the computer.
- [x] Recognize, confirm when necessary, and transform source coordinate reference systems without modifying the source data.
- [x] Recommend filters and thresholds before applying them.
- [x] Preserve every source observation and record why each observation was accepted or excluded.
- [x] Reconstruct harvest passes when a reliable source pass identifier is unavailable.
- [x] Require a field boundary for the final cleaning operation, while allowing it to be selected, digitized, or derived from the yield data.
- [x] Accept an existing field boundary from either a layer already loaded in QGIS or a file selected from the computer.
- [x] Exclude observations outside the accepted field boundary from cleaned output without deleting them from the audit layer.
- [x] Create a portable interactive HTML review for every successful run.
- [x] Modernize the USDA Yield Editor workflow rather than reproduce legacy behavior exactly.
- [x] Evaluate AgGateway ADAPT for interoperable input and output.
- [x] Preserve a future path for user-authorized equipment-platform connections, beginning with John Deere Operations Center.

### Current development state

- [x] USDA Yield Editor source tree inventoried.
- [x] Legacy filter families and unavailable OCX dependencies identified.
- [x] Existing public QGIS plugins reviewed for structure, versioning, licensing, Processing registration, packaging, and HTML review patterns.
- [x] Current ADAPT Toolkit and ADAPT Standard roles reviewed.
- [x] CRS recognition, confirmation, transformation, and provenance requirements defined.
- [x] QGIS Plugin Repository security review included as a release gate.
- [x] Future John Deere pull and additive write-back architecture defined.
- [x] Initial phased specification created.
- [x] Local workspace initialized from and connected to the public Git repository.
- [x] Plugin package scaffolded.
- [ ] Real raw yield-monitor datasets collected for implementation fixtures and validation.
- [x] Version 0.1.0 implemented and validated locally as an experimental development build.
- [ ] Version 1.0.0 validated and published.

## 2. Product purpose

Yield Data Cleaner will convert raw or partially processed combine yield-monitor
records into an auditable, spatially consistent field dataset. It will guide a
user through input recognition, field-boundary selection or creation, pass
reconstruction, filter recommendations, manual review, cleaning, export, and an
interactive before/after report.

The plugin is inspired by the filtering concepts and workflow of USDA-ARS Yield
Editor 2, but it will be a new Python/PyQGIS implementation designed for current
QGIS versions, current geospatial formats, transparent filter provenance, and
public open-source distribution.

### Primary user

A farmer, crop consultant, agronomist, researcher, or GIS analyst using QGIS who
has yield-monitor data for one field and needs to understand and clean it without
silently destroying source observations.

### Version 1 outcome

A successful run produces:

1. A validated field boundary.
2. A canonical point dataset containing every source observation.
3. A cleaned point layer containing accepted observations.
4. An excluded-observation layer with one or more explicit filter reasons.
5. Reconstructed or source-derived harvest passes.
6. A versioned filter recipe and run manifest.
7. Summary tables and optional interchange exports.
8. A portable HTML review comparing raw and cleaned results.

## 3. Scope

### Included in version 1

- One field per run.
- Existing QGIS-readable point layers.
- Generic delimited text files, including CSV and TXT.
- Automatic delimiter, coordinate, time, field, unit, and measurement-column detection.
- Reusable vendor and user mapping profiles.
- Initial Ag Leader and John Deere/GreenStar text presets when representative files are available.
- ADAPT Standard import and export where the source or result satisfies the standard.
- Corn, soybean, and wheat crop properties.
- Imperial and Metric units.
- Existing, digitized, or data-derived field boundaries.
- All core USDA Yield Editor filter families, reimplemented and modernized.
- Automatic recommendations with user confirmation.
- Manual point exclusion and restoration.
- Non-destructive, reason-coded outputs.
- Interactive dialog and Processing Toolbox algorithm.
- Portable HTML review.
- Saved run recipes for repeatability.
- Public release packaging, tests, documentation, and QGIS Plugin Repository readiness.

All filter capabilities are part of the 1.0 target. The implementation phases
below are incremental pre-1.0 deliveries, not deferrals beyond version 1.

### Not promised in version 1 without validated examples

- Direct support for every proprietary monitor binary or backup format.
- Cloud account connections to equipment manufacturers in the 1.0 release. These are a documented post-1.0 roadmap item.
- Reverse engineering encrypted or undocumented vendor formats.
- Batch processing of multiple fields in one run.
- Agronomic interpolation or creation of a continuous yield surface.
- Correction of monitor calibration when the necessary calibration evidence is absent.
- A claim that cleaned data is scientifically correct solely because filters completed.

## 4. Reference implementations and licensing boundary

### USDA Yield Editor

The local `YE2code` source is a scientific and workflow reference. Its available
source includes filtering, mapping, configuration, import, export, overlap, and
local outlier logic. The original program also depended on a proprietary strip
chart control and a separately supplied phase-correlation OCX whose source is not
available.

The project will:

- Reimplement filter behavior in testable Python rather than wrap the VB6 executable.
- Exclude all unavailable OCX binaries and proprietary components.
- Independently implement and validate automated delay estimation.
- Document where a method is derived from or materially influenced by Yield Editor.
- Include a `THIRD_PARTY_NOTICES.md` file before public release.
- Confirm the reuse status of the supplied USDA source before copying any substantial source expression verbatim.

### Existing project patterns

The plugin will reuse architectural patterns, not product-specific code, from:

- **Fake Farm Data Generator:** Processing provider, toolbar launch action, guided dialog, portable Leaflet review, packaging scripts, release-version checks, CI, and QGIS smoke tests.
- **Field Water Erosion Calculator:** separation of core, processing, report, UI, settings, provenance, and run-package responsibilities.
- **Field Boundary Tools:** QGIS 3/QGIS 4 compatibility helpers, public-plugin metadata, upload-security checks, and HTML comparison patterns.

### Project license

- Plugin source: GPL-3.0-or-later.
- Every distributed Python file will carry `SPDX-License-Identifier: GPL-3.0-or-later`.
- The full license will exist at the repository root and inside the packaged plugin directory.
- Vendored browser assets will retain their own licenses and notices.
- No proprietary vendor parser or ADAPT plugin will be redistributed without a compatible license.

## 5. AgGateway ADAPT decision

### Decision

Use the **ADAPT Standard** as an interchange target and supported adapter, but do
not make the QGIS plugin depend on the legacy .NET ADAPT Toolkit.

### Rationale

The current ADAPT Standard is data-only and uses a JSON root with GeoParquet and
GeoTIFF spatial files. It is a better fit for a Python/QGIS plugin than the older
ADAPT Toolkit, which is implemented for .NET and relies on format plugins.

The ADAPT harvest model is principally a processed exchange model. It expects the
data producer to have already applied known sensor calibrations and sensor
latencies such as yield flow delay. Harvest work records use coverage polygons,
not raw monitor points, for the mapped operation. Therefore:

- ADAPT Standard is a strong **cleaned output** option.
- ADAPT Standard input may be supported when an existing ADAPT package contains suitable harvest data.
- ADAPT Standard is not a replacement for the plugin's raw point schema or audit trail.
- Raw monitor delay, header state, and rejected observations remain in the plugin's GeoPackage and manifest even when the cleaned result is exported to ADAPT.
- ADAPT coverage polygons will be generated only after cleaning, using accepted observations, swath geometry, and the accepted field boundary.

### Legacy ADAPT Toolkit

The older ADAPT Framework and its plugins may later be used through an optional
external conversion bridge when that provides access to a useful vendor or
ISOXML parser. It will not be bundled into the core plugin because it adds a .NET
runtime boundary, has a different license, and does not remove the need for the
plugin's canonical raw-observation model.

### ADAPT deliverables

- [ ] Record the supported ADAPT Standard version in code and run manifests.
- [ ] Map canonical crop, field, operation, time, device, and yield values to ADAPT definitions.
- [ ] Import supported ADAPT harvest packages.
- [ ] Export cleaned harvest coverage as ADAPT JSON plus GeoParquet.
- [ ] Validate output against official schemas and scenario examples.
- [ ] Preserve unit definitions required by ADAPT while displaying Imperial values by default in the UI.
- [ ] Complete a license review before bundling any ADAPT schemas or example assets.
- [ ] Evaluate the legacy Toolkit/ISOXML plugin as an optional external bridge after the native importers are stable.

## 6. User workflow

### Step 1 - Select source data

The input control provides two primary paths:

1. **Use a loaded QGIS layer:** choose an eligible point layer already present in the current QGIS project.
2. **Browse for a file:** select a supported file or package from the computer without first adding it to QGIS.

Supported sources include:

- A point layer already loaded in QGIS.
- A supported vector file.
- A CSV or other delimited text file.
- An ADAPT Standard package.
- A supported vendor export recognized by an importer profile.

The plugin inventories the source without altering it.

### Step 2 - Recognize and map columns

The plugin proposes mappings for:

- X/longitude and Y/latitude, or existing geometry.
- Timestamp, date, time, or source sequence.
- Source pass, track, load, or operation identifier.
- Wet yield, dry/standard-moisture yield, mass flow, or volume flow.
- Commodity moisture.
- Ground speed, distance, and observation duration.
- Swath or header width.
- Header/implement engaged state.
- Heading or travel direction.
- Elevation.
- Crop.
- Machine/device identifier.

Each proposal receives a confidence value and an explanation. High-confidence
mappings may be preselected. Missing, ambiguous, or conflicting mappings must be
shown to the user before the run continues. User-confirmed mappings can be saved
as reusable profiles identified by vendor, display/software export, and schema
signature.

### Step 3 - Recognize and normalize the CRS

The plugin must recognize and safely transform the source coordinate reference
system before distance, area, pass, swath, overlap, boundary, or local-neighborhood
calculations occur.

#### CRS recognition order

1. Use the valid CRS assigned to an already loaded QGIS layer.
2. Read embedded or companion CRS metadata such as GeoPackage metadata, a Shapefile `.prj`, or another format-supported definition.
3. Use an explicit CRS declared by a supported vendor or ADAPT format.
4. For delimited coordinates, evaluate column names, numeric ranges, hemisphere, vendor profile, field-boundary location, and project context.
5. Ask the user to select or confirm the source CRS whenever it is missing, invalid, conflicting, or below the recognition-confidence threshold.

The plugin must not silently assign a CRS from coordinate ranges alone when more
than one reasonable interpretation exists. It must detect likely longitude/latitude
axis reversal and present the proposed correction for confirmation.

#### Transformation rules

- Preserve original coordinate values, source geometry, and source CRS metadata in the audit record.
- Transform a working copy through `QgsCoordinateTransform` and the active QGIS transform context.
- Allow the yield layer and field boundary to begin in different valid CRSs.
- Select an appropriate local projected analysis CRS for distance and area calculations; record how it was selected.
- Transform review data to EPSG:4326 only where required by the portable web map or an interchange specification.
- Allow a user-selected output CRS while keeping the analysis CRS independent from the display/output choice.
- Stop with a clear validation error when a transformation fails, produces non-finite coordinates, places the data outside a plausible field extent, or lacks a required datum operation.
- Record source CRS, boundary CRS, analysis CRS, output CRS, coordinate operation, axis handling, and transformation warnings in the run manifest.

### Step 4 - Confirm crop and units

The user confirms:

- Corn, soybean, or wheat.
- Source unit system and per-column units.
- Standard market moisture.
- Test weight or mass/volume conversion assumptions when bushel-based values are used.

Internal calculations use explicit canonical units. Display and export units are
separate settings. Every conversion and crop assumption is recorded in the run
manifest.

### Step 5 - Establish the field boundary

A valid field boundary is required before final filtering and export. The user can
choose one of three modes.

#### A. Select an existing boundary

- Choose a polygon layer already loaded in QGIS or browse to a polygon file on the computer.
- Select exactly one polygon feature when the chosen source contains multiple features.
- Repair safe geometry defects when possible and report every repair.
- Reject empty, invalid, or implausibly small geometry.
- Recognize the boundary CRS independently and transform both boundary and observations into the selected analysis CRS.

#### B. Derive a boundary from the yield data

- Perform positional preflight and establish observation order.
- Use engaged observations and reconstructed swath footprints when width is available.
- Dissolve the footprints, close small internal gaps, remove small isolated fragments, and simplify only within documented tolerances.
- Fall back to a reviewed concave-hull method when swath geometry cannot be built.
- Calculate a derivation confidence score and list the assumptions used.
- Show the proposed boundary over the observations and require user acceptance or editing.

The derived boundary is an operational harvest extent, not automatically a legal,
ownership, FSA, or permanent management boundary.

#### C. Digitize a boundary

- Draw a polygon on the QGIS map canvas.
- Validate and preview it before continuing.

#### Boundary clipping rule

Observations outside the accepted boundary are flagged `outside_boundary` and are
not included in cleaned output. They remain in `all_observations` with their
original geometry and values. A configurable geometric tolerance may protect
against small GNSS offsets at the boundary, but the tolerance and its units must
be visible and recorded.

### Step 6 - Reconstruct or validate passes

When a trustworthy source pass ID exists, the plugin validates its sequence and
spatial coherence. Otherwise it reconstructs passes using available evidence:

- Timestamp or source order.
- Time and distance gaps.
- Heading changes and turn detection.
- Header state.
- Speed.
- Swath continuity.
- Machine identifier.

Every point receives a `pass_id`, `pass_source`, and `pass_confidence`. Low-confidence
splits or merges are presented for review.

### Step 7 - Recommend cleaning settings

The plugin computes suggested thresholds and displays:

- Recommended value.
- Evidence or distribution used.
- Number and percentage of observations affected.
- Map preview.
- Warning when the estimate is unstable or the required source field is absent.

Recommendations do not silently become accepted truth. The user can enable,
disable, or edit each filter before execution.

### Step 8 - Preview, manually review, and run

The user sees raw and provisionally accepted observations in QGIS. A filter-reason
panel can isolate observations affected by any rule. The user may manually exclude
or restore observations, with manual decisions recorded separately from automated
rules.

### Step 9 - Save outputs and open the review

The user chooses an output folder. The plugin remembers the previous location but
never overwrites an existing completed run silently. On success it adds primary
layers to QGIS and offers actions to open the HTML review or output folder.

## 7. Canonical data model

The cleaning engine will operate on a vendor-neutral canonical observation model.
Source fields remain unchanged and are accompanied by normalized fields.

### Required canonical identity fields

- `observation_id`: stable identifier within the run.
- `source_index`: original record number or feature ID.
- `source_name`: input file or layer.
- `geometry_original`: source geometry retained by the source/audit representation.
- `source_crs`: authoritative source CRS identifier or definition.
- `analysis_crs`: projected CRS used for spatial cleaning calculations.
- `crs_confidence`: `declared`, `recognized`, `user_confirmed`, or `unresolved`.
- `timestamp_utc` or `source_sequence`.
- `crop_code`.
- `unit_profile`.

### Measurement fields when available

- `yield_wet_mass_area`
- `yield_dry_mass_area`
- `mass_flow_wet`
- `mass_flow_dry`
- `moisture_pct`
- `speed_m_s`
- `distance_m`
- `duration_s`
- `swath_width_m`
- `heading_deg`
- `header_engaged`
- `elevation_m`

### Cleaning and provenance fields

- `clean_status`: `accepted`, `excluded`, `review`, or `unavailable`.
- `filter_flags`: stable integer or text bit-set representation.
- `filter_reasons`: ordered machine-readable reason codes.
- `filter_count`.
- `manual_action`: `none`, `exclude`, or `restore`.
- `pass_id`.
- `pass_source`: `source`, `reconstructed`, or `manual`.
- `pass_confidence`.
- `corrected_yield`.
- `corrected_moisture`.
- `flow_delay_s`.
- `moisture_delay_s`.
- `boundary_status`.
- `recipe_version`.
- `plugin_version`.

Missing inputs are represented as unavailable, never as zero or as a successful
filter result.

## 8. Cleaning engine

Filters are deterministic stages operating on the canonical model. Each stage
returns flags, diagnostics, and summary counts. A later stage may use prior flags
but cannot erase their provenance.

### Filter families required for version 1

#### Input and position quality

- Missing or invalid geometry.
- Non-finite numeric values.
- Duplicate observations.
- Implausible coordinate jumps.
- Invalid or reversed timestamp sequence.
- Outside accepted field boundary.

#### Sensor delay and pass-edge behavior

- Flow/yield sensor delay correction.
- Moisture sensor delay correction.
- Start-of-pass exclusion.
- End-of-pass exclusion.
- Confidence and stability diagnostics for automatically estimated delays.

Automated delay estimation must be a new, documented implementation. If the
estimate is unstable, the UI recommends review or a manual setting instead of
quietly applying it.

#### Motion and swath

- Minimum speed.
- Maximum speed.
- Sudden speed-change filter.
- Minimum valid swath width.
- Implausible width changes.
- Header up or implement disengaged.

#### Yield and moisture ranges

- Crop-aware absolute minimum yield.
- Crop-aware absolute maximum yield.
- User threshold overrides.
- Moisture minimum and maximum when moisture is present.
- Explicit handling of wet, dry, and standard-moisture values.

#### Spatial consistency

- Harvest overlap based on reconstructed coverage/swath footprints.
- Local yield outlier filter using a documented neighborhood and robust statistic.
- Position outlier detection.
- Optional low-confidence pass review.

#### Manual review

- Select observations on the map and exclude them.
- Restore observations excluded by an automated filter.
- Preserve both automated reasons and the final manual action.

### Filter order

The versioned recipe defines filter order. The initial order is:

1. Schema and numeric validation.
2. Position and time validation.
3. Boundary establishment and outside-boundary flagging.
4. Pass validation or reconstruction.
5. Header and motion filters.
6. Delay correction.
7. Pass start/end filters.
8. Swath and overlap analysis.
9. Crop-aware yield and moisture ranges.
10. Local spatial outliers.
11. Manual decisions.
12. Final accepted/excluded classification and summaries.

Changing the scientific meaning or order of a stage requires a recipe-schema
version change and migration notes.

## 9. Outputs

Each run creates a new folder with a collision-safe name such as:

`<field-or-boundary>_<crop>_<YYYY-MM-DD>/`

The field component is suggested from the selected boundary layer or file and is
editable before the run. If that folder already exists, the plugin creates
`_02`, `_03`, and so on instead of blocking the user or overwriting an earlier or
partial run. Primary files repeat the run-folder name so they remain identifiable
when copied elsewhere.

### Required files

#### `<run-folder-name>_yield_data.gpkg`

- `field_boundary`: accepted input, digitized, or derived boundary.
- `all_observations`: every source observation plus canonical and cleaning fields.
- `accepted_observations`: observations included in the cleaned dataset.
- `excluded_observations`: observations not included, with reason codes.
- `harvest_passes`: reconstructed or source-derived pass lines and diagnostics.
- `harvest_coverage`: accepted swath/coverage polygons when they can be reliably generated.

#### Audit and summary files

- `<run-folder-name>_run_manifest.json`
- `<run-folder-name>_cleaning_recipe.json`
- `<run-folder-name>_column_mapping.json`
- `<run-folder-name>_filter_summary.csv`
- `<run-folder-name>_yield_cleaning_review.html`
- `<run-folder-name>_yield_cleaning_review_data/`
- `<run-folder-name>_run_log.txt`

### Optional exports

- Cleaned CSV with original and normalized fields.
- Cleaned GeoPackage point layer selected separately from the run package.
- GeoJSON for smaller datasets.
- GeoParquet when supported by the installed QGIS/GDAL environment.
- ADAPT Standard package containing processed harvest coverage.
- Shapefile only with an explicit warning about field-name, type, null, and file-size limitations.

## 10. Portable HTML review

The review will use locally packaged, license-preserved Leaflet assets and local
data files. It must open from `file://` without a local web server. Online
basemaps are optional enhancements; review data, controls, legends, and summaries
must still load offline.

### Required review capabilities

- Raw-versus-cleaned swipe comparison.
- Switchable display attributes: raw yield, corrected yield, moisture, speed, swath width, pass, and cleaning status.
- Toggle accepted, excluded, review, and individual filter-reason categories.
- Click an observation to inspect original values, normalized values, corrections, and every filter reason.
- Show field boundary, pass lines, and coverage footprints where available.
- Show total, accepted, excluded, and review counts and percentages.
- Show raw and cleaned acreage, harvested mass, and mean yield with clear unit labels and calculation assumptions.
- Show raw and cleaned histograms for yield, moisture, and speed.
- Show filter-by-filter counts, thresholds, and recommendation confidence.
- Show plugin version, recipe version, input signature, run time, CRS, unit profile, crop assumptions, and boundary source.
- Explain deterministic review sampling when the browser view contains fewer observations than the GeoPackage.
- Provide a collapsible information panel and responsive layout.

### Review safety and integrity

- Escape all source-derived text before placing it in HTML or JavaScript.
- Do not load executable code from user-supplied fields.
- Vendor JavaScript and CSS rather than depend on a CDN.
- Record total and displayed feature counts separately.
- Never describe a canceled or failed run as completed.
- Keep the HTML file and companion data directory together.

## 11. QGIS interfaces

### Guided dialog

The toolbar/menu action opens one staged dialog. The user-facing term
**Prepare Dataset** replaces **Canonical Audit**; canonical remains an internal
schema and implementation term. Initial and future tabs are:

1. Input & Mapping (including CRS, crop, and unit review)
2. Field Boundary
3. Prepare Dataset (named output location and initial prepared run)
4. Passes
5. Filter Recommendations
6. Map / Manual Review
7. Clean & Export
8. Completion

The dialog uses the same engine and recipe as the Processing algorithm. It must
not contain a separate implementation of cleaning logic.

### Processing provider

The plugin registers a `Yield Data Cleaner` provider. Version 1 includes at least:

- `Clean yield monitor data`
- `Create or derive field boundary from yield data`
- `Inspect and map yield data columns`
- `Export cleaned yield data to ADAPT Standard`

The primary algorithm accepts a mapping/recipe file so advanced users can run a
repeatable process without stepping through the dialog.

## 12. Proposed source layout

```text
yield_data_cleaner/
  __init__.py
  metadata.txt
  plugin.py
  provider.py
  version.py
  LICENSE
  algorithms/
    clean_yield_data.py
    derive_field_boundary.py
    inspect_yield_columns.py
    export_adapt.py
  core/
    canonical_schema.py
    crop_profiles.py
    crs_service.py
    errors.py
    filter_engine.py
    filter_flags.py
    identifiers.py
    pass_reconstruction.py
    provenance.py
    recommendations.py
    run_package.py
    settings.py
    units.py
  boundaries/
    boundary_service.py
    coverage_builder.py
    derivation.py
  filters/
    boundary.py
    delays.py
    header.py
    local_outlier.py
    overlap.py
    position.py
    ranges.py
    speed.py
    swath.py
  importers/
    adapt_standard.py
    column_detection.py
    delimited_text.py
    profiles.py
    vector.py
    vendors/
      agleader.py
      greenstar.py
  exporters/
    adapt_standard.py
    delimited_text.py
    vector.py
  review/
    builder.py
    static/
  ui/
    cleaner_dialog.py
    column_mapping_page.py
    boundary_page.py
    filter_review_page.py
    map_review.py
  resources/
  help/
tests/
tools/
docs/
.github/workflows/
```

Core calculations should remain independently testable without launching the
full QGIS desktop interface wherever practical. QGIS-specific adapters convert
layers and features to and from the canonical model.

## 13. Versioning and release policy

### Version milestones

- `0.1.0`: installable scaffold, provider, dialog shell, canonical schema, generic point/CSV import, mapping preview.
- `0.2.0`: crop/units system and complete boundary workflow.
- `0.3.0`: pass reconstruction and source pass validation.
- `0.4.0`: core motion, header, swath, range, and pass-edge filters.
- `0.5.0`: delay estimation/correction and overlap analysis.
- `0.6.0`: local spatial outliers, manual review, and recipe persistence.
- `0.7.0`: complete output package and portable HTML review.
- `0.8.0`: ADAPT Standard import/export and initial vendor presets.
- `0.9.0`: real-data validation, performance work, documentation, compatibility, and release candidate.
- `1.0.0`: validated public release.

Milestone numbers describe planned compatibility checkpoints. They may be
combined when a coherent delivery is ready, but version numbers must never claim
completion of an unchecked acceptance gate.

### Version synchronization

- `metadata.txt` is the packaged plugin version source.
- `version.py`, documentation, changelog, release notes, ZIP name, and Git tag must match it.
- CI runs a release-version verifier.
- Tags follow `vMAJOR.MINOR.PATCH`.
- Scientific recipe and output schema versions are tracked separately from the plugin version.
- Breaking recipe or output-schema changes require migrations or an explicit compatibility error.

### QGIS compatibility target

- Target minimum: QGIS 3.28.
- Target maximum metadata value: QGIS 4.99.
- Test supported QGIS 3 LTR/current versions and QGIS 4 preview/current images available to CI.
- Use scoped Qt6/PyQGIS enums with compatibility fallbacks where required.
- Do not claim a QGIS version is supported until its smoke test or documented manual validation passes.

### QGIS Plugin Repository security-review policy

Security and upload compatibility are continuous development requirements, not a
single scan performed after the release is already packaged.

- Parse every distributed Python file and reject UTF-8 BOM or syntax failures before interpreting checker results.
- Run static security checks against both the source package and the exact ZIP intended for upload.
- Run the official or current QGIS plugin metadata, archive, dependency, and Qt6/PyQGIS compatibility checks available for the target repository workflow.
- Treat an incomplete or crashed checker as a failure, not as a clean result.
- Validate archive member paths and reject traversal, unexpected binaries, caches, credentials, private data, and development-only files.
- Use scoped Qt6 enums with tested QGIS 3 fallbacks.
- Allow only documented HTTPS network endpoints, bounded timeouts, validated redirects, and clear offline behavior.
- Never embed API client secrets, access tokens, refresh tokens, farm credentials, or private keys in source code or release archives.
- Escape source-derived HTML and JavaScript content and vendor browser dependencies with their license files.
- Document and narrowly scope any static-analysis suppression at the validated sink, with a regression test proving the safety boundary.
- Preserve a generated security-review record identifying the source commit, plugin version, ZIP checksum, tools, and results.
- Do not publish or upload a release until every actionable finding is fixed or explicitly documented and accepted with evidence.

## 14. Phased delivery plan

### Phase 0 - Research, specification, and repository foundation

- [x] Inventory USDA Yield Editor source and filters.
- [x] Identify missing/proprietary legacy dependencies.
- [x] Review existing plugin architecture and public-release patterns.
- [x] Review ADAPT Toolkit versus ADAPT Standard.
- [x] Confirm product name, repository, public-release intent, one-field scope, boundary behavior, and output-folder workflow.
- [x] Create this specification.
- [x] Clone/connect the local workspace to the public repository without losing `YE2code`.
- [x] Add repository `LICENSE`, `.gitignore`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, and `THIRD_PARTY_NOTICES.md`.
- [x] Record the USDA source as a non-packaged reference and ensure release archives exclude legacy binaries and OCX references.
- [x] Add issue and pull-request templates.
- [ ] Add source/ZIP security scanning, Python parse/BOM checks, archive inspection, and Qt6 compatibility checks to CI.

**Phase 0 exit gate:** repository foundation is public, licensed, documented, and contains no accidentally distributed proprietary component.

### Phase 1 - Installable plugin and canonical import vertical slice (0.1.0)

- [x] Create package metadata with `experimental=True`.
- [x] Register the Processing provider.
- [x] Add branded toolbar/menu action and guided dialog shell.
- [x] Implement canonical observation schema and stable reason-code registry.
- [x] Select and import eligible point layers already loaded in QGIS.
- [x] Browse for and import generic vector and delimited files from the computer.
- [x] Detect delimiter, geometry fields, CRS definitions/hints, and common yield columns.
- [x] Implement CRS confidence, user confirmation, axis-order review, analysis-CRS selection, and safe transformation.
- [x] Preserve source coordinates and CRS provenance in the prepared observation layer and manifest.
- [x] Build column-mapping review and save/load mapping profiles.
- [x] Create a minimal run manifest.
- [x] Add unit tests, plugin-structure tests, packaging tool, and archive validator.

**Phase 1 exit gate:** a user can install the plugin, choose a loaded layer or browse for a generic point/CSV dataset, review mappings and CRS handling, and create a transformed prepared dataset without cleaning it.

### Phase 2 - Crop, units, and boundary workflow (0.2.0)

- [x] Implement corn, soybean, and wheat profiles.
- [x] Implement centralized Imperial/Metric conversions.
- [x] Validate market-moisture and test-weight assumptions.
- [x] Select and validate an existing single-field polygon from a loaded layer or a file chosen from the computer.
- [x] Derive coverage footprints from ordered points and swath width.
- [x] Derive a reviewed boundary from point/swath footprints or concave-hull fallback.
- [x] Calculate derivation confidence and provenance.
- [x] Flag outside-boundary points while retaining them in the audit layer.
- [x] Transform independently defined yield and boundary CRSs into the analysis CRS before clipping or geometry calculations.
- [x] Add boundary-focused tests for projected CRS, geometry repair, edge tolerance, holes, multipart inputs, and GNSS offsets.
- [x] Test geographic/projected inputs, missing CRS, conflicting CRS, axis reversal, datum transforms, and independently projected boundaries.

**Phase 2 exit gate:** every run has a user-accepted boundary and reproducible boundary provenance, and outside observations are non-destructively excluded.

### Phase 3 - Pass reconstruction (0.3.0)

- [x] Validate source pass identifiers.
- [x] Implement time-gap, distance-gap, heading-change, header-state, and continuity evidence.
- [x] Reconstruct passes when source IDs are absent or unusable.
- [x] Produce pass lines, confidence values, and diagnostics.
- [x] Add guided review for low-confidence splits and merges.
- [x] Test multi-day data, stopped combines, turns, adjacent passes, missing timestamps, and multiple machine IDs.

**Phase 3 exit gate:** pass assignments are stable, inspectable, and never represented as source-provided when inferred.

### Phase 4 - Core filters and recommendations (0.4.0)

- [x] Implement schema/numeric validity filters.
- [x] Implement duplicate and position-jump filters.
- [x] Implement header-state filter.
- [x] Implement minimum/maximum/sudden-change speed filters.
- [x] Implement swath-width filters.
- [x] Implement start/end-of-pass filters.
- [x] Implement crop-aware yield range filters.
- [x] Implement moisture range filters.
- [x] Generate recommended thresholds with counts, evidence, and confidence.
- [x] Add filter preview and user overrides.
- [x] Persist a versioned recipe.

**Phase 4 exit gate:** core rules can be previewed and reproduced, and every exclusion has stable reason codes.

### Phase 5 - Delay, overlap, local outliers, and manual decisions (0.5.0-0.6.0)

- [x] Implement manual flow-delay input.
- [x] Implement manual moisture-delay input.
- [x] Implement independently designed automatic delay estimation.
- [x] Report delay-estimate stability and refuse unsafe automatic application.
- [x] Implement swath/coverage overlap detection.
- [x] Implement robust local spatial outlier detection.
- [x] Add QGIS map selection for manual exclusion and restoration.
- [x] Preserve automated flags after manual restoration.
- [x] Compare modern filter behavior with legacy Yield Editor concepts on controlled fixtures.

**Phase 5 exit gate:** all version 1 filter families operate non-destructively, automated delay estimation is confidence-gated, and manual decisions remain fully auditable.

### Phase 6 - Outputs and HTML review (0.7.0)

- [x] Write all required GeoPackage layers.
- [x] Write manifest, recipe, mapping, summary, and log files.
- [x] Add optional CSV, GeoJSON, GeoParquet, and Shapefile exports with format warnings.
- [x] Build portable Leaflet assets and data writer.
- [x] Add raw/cleaned swipe review.
- [x] Add attribute styling, reason toggles, observation popups, boundary, pass, and coverage display.
- [x] Add statistics and histograms.
- [x] Add deterministic browser sampling and displayed/total counts.
- [x] Add completion actions to open the review or output folder.
- [x] Test offline opening, path portability, HTML escaping, large feature counts, canceled runs, and incomplete outputs.

**Phase 6 exit gate:** every successful run creates a portable, safe, accurate before/after review and complete audit package.

### Phase 7 - ADAPT and vendor interoperability (0.8.0)

- [x] Implement supported ADAPT Standard harvest import.
- [x] Generate accepted harvest coverage polygons suitable for ADAPT export.
- [x] Implement ADAPT Standard JSON and GeoParquet export.
- [x] Validate against official schema and examples.
- [x] Implement Ag Leader text profile from real samples.
- [x] Implement John Deere/GreenStar text profile from real samples.
- [x] Document recognized variants and explicit unsupported cases.
- [x] Evaluate optional legacy ADAPT Toolkit/ISOXML bridge without adding a mandatory .NET dependency.

**Phase 7 exit gate:** standard interchange and each advertised vendor profile pass fixture and round-trip/semantic validation appropriate to the format.

### Phase 8 - Real-data validation and public release (0.9.0-1.0.0)

- [ ] Collect legally shareable or private-test raw datasets covering all three crops and multiple monitor/export sources.
- [ ] Create sanitized regression fixtures that contain no private farm information.
- [ ] Compare outputs with expert-reviewed cleaning decisions.
- [ ] Report filter-by-filter agreement and disagreement rather than only final point counts.
- [ ] Verify field totals, area, harvested mass, and mean-yield calculations.
- [ ] Benchmark realistic small, medium, and large field datasets.
- [ ] Validate cancellation and recovery behavior.
- [x] Run Python unit/integration tests.
- [ ] Run QGIS smoke-test matrix.
- [x] Run QGIS Plugin Repository metadata, archive, security, and Qt6 compatibility checks.
- [x] Confirm every distributed Python file parses and no checker terminated early or skipped files.
- [x] Scan and inspect the exact release ZIP, record its checksum, and verify that it contains no secrets, private fixtures, legacy OCX files, caches, or unexpected binaries.
- [ ] Visually inspect the dialog and HTML review on Windows, Linux, and macOS where available.
- [ ] Complete user guide, sample data, methodology, known limitations, privacy statement, and release notes.
- [ ] Remove `experimental=True` only after acceptance gates pass.
- [ ] Package, checksum, tag, and publish version 1.0.0.

**Phase 8 exit gate:** version 1 claims are supported by real-data evidence, compatibility results, archive inspection, and public documentation.

## 15. Validation strategy

### Test layers

1. Pure-Python tests for units, crop profiles, filter decisions, reason flags, recommendations, recipes, and statistics.
2. Geometry tests for boundary derivation, clipping, coverage, overlap, and passes.
3. Importer contract tests using sanitized fixtures.
4. QGIS integration tests for layers, Processing algorithms, output GeoPackages, and CRS handling.
5. HTML tests for escaping, manifest agreement, feature counts, portability, and required controls.
6. Installed-plugin smoke tests in supported QGIS versions.
7. Expert-reviewed real-data comparisons.

### Scientific reporting

Validation reports will separate:

- Input recognition accuracy.
- Pass reconstruction accuracy.
- Filter-specific agreement.
- Accepted/excluded classification agreement.
- Field mean and total differences.
- Within-field spatial pattern changes.
- Boundary and coverage differences.
- Runtime and memory performance.

A visually smoother map is not evidence that the cleaning is correct.

## 16. Privacy and security

- Processing is local by default.
- No yield data is uploaded by the plugin for core operation.
- Optional online basemaps do not receive the yield attributes, but their tile providers may receive map-tile requests for the viewed location; this must be disclosed.
- HTML source values are escaped.
- Archives and external input paths are validated before extraction or use.
- Vendor filenames, grower names, farm names, coordinates, and device identifiers must be removed from public fixtures unless explicitly authorized.
- Output folders never overwrite completed runs without explicit user action.
- Network features, if later added, use HTTPS, bounded timeouts, allowlisted hosts, and clear offline fallback.

## 17. Documentation required for 1.0

- [x] README with installation and quick start.
- [x] User guide for the interactive workflow.
- [x] Processing algorithm reference.
- [x] Supported input formats and column mapping guide.
- [x] Crop and unit assumptions.
- [x] Filter methodology and order.
- [x] Boundary derivation methodology and limitations.
- [x] ADAPT import/export documentation.
- [x] Output schema and reason-code reference.
- [x] Validation report.
- [x] Compatibility report.
- [x] Privacy and security notes.
- [x] CONTRIBUTING guide.
- [x] CHANGELOG and release notes.
- [x] Third-party notices.

## 18. Data needed from the project owner

Real raw data is not required to scaffold the plugin, canonical schema, generic
importer, or test harness. It is required before vendor profiles and scientific
filter behavior can be considered validated.

Useful examples include:

- Raw Ag Leader yield exports.
- Raw John Deere/GreenStar yield exports.
- CSV or Shapefile exports from other monitors or farm software.
- Data with and without explicit pass IDs.
- Data with header state, mass flow, moisture, speed, width, and timestamps.
- Fields containing known stops, turns, overlaps, partial swaths, sensor delay, and obvious bad positions.
- A corresponding field boundary when available.
- Expert-cleaned or previously accepted output when available.

Before any sample becomes a committed fixture, verify that it is permitted for
public distribution and remove private farm identifiers and precise locations.

## 19. Future equipment-platform integrations

Equipment-platform connections are a post-1.0 capability. The version 1 engine,
canonical schema, recipes, run packages, and import/export adapters must be built
so a future connector can supply input without changing the cleaning science.

### Intended user workflow

1. The user chooses **Connect equipment platform** and completes the provider's authorization in the system browser.
2. The user explicitly selects an authorized organization/account, field, crop season, and harvest operation.
3. The connector downloads the selected yield data and its boundary/metadata into a new local run package.
4. Yield Data Cleaner performs the same mapping, CRS review, boundary review, recommendations, manual review, and non-destructive cleaning used for local files.
5. The user may keep the result local or choose **Send cleaned result back**.
6. Before any upload, the plugin shows the exact destination, format, filename/layer name, field, season, included records, excluded records, units, CRS, and remote permissions.
7. A send-back operation requires separate explicit confirmation and creates a new remote artifact; it never silently overwrites or deletes the original operation.
8. The connector reads back the created resource or upload status and writes an immutable receipt to the local run manifest.

### John Deere Operations Center feasibility

John Deere is the first planned connector. Its official Field Operations API can
list harvest operations and export point- or polygon-based Shapefiles, including
measurement metadata and units. Deere documents those Shapefiles as WGS84
(EPSG:4326), so the normal CRS recognition and analysis transformation still
apply after download.

The official Files API supports creating a file record and uploading file content,
and the Map Layers API supports contributed map-layer resources. These APIs make
additive send-back technically plausible, subject to application approval,
customer authorization, scopes, supported Deere formats, access tier, and
sandbox/production validation. Upload capability must not be described as the
ability to replace or rewrite the original Deere-processed Field Operation.

Official references:

- [John Deere Field Operations API](https://developer.deere.com/dev-docs/field-operations)
- [John Deere Files API](https://developer.deere.com/dev-docs/files)
- [John Deere Map Layers API](https://developer.deere.com/dev-docs/map-layers)

### Authentication architecture

John Deere's external application flow uses OAuth 2 authorization code grants and
requires a registered application ID, client secret, redirect URI, requested
scopes, and a separate customer organization-connection decision. A client secret
cannot be safely embedded in a public QGIS plugin.

The production design therefore requires a small separately deployed integration
service that:

- Holds the provider client secret outside the plugin and repository.
- Starts browser authorization with a high-entropy state value and registered HTTPS callback.
- Exchanges authorization codes and refreshes tokens server-side.
- Encrypts tokens at rest and separates them by user and provider organization.
- Gives the QGIS plugin only bounded, task-specific sessions or short-lived download/upload authorization.
- Requests the minimum scopes needed for the action currently selected.
- Supports disconnect and provider-side revocation.
- Never logs tokens, authorization codes, yield payloads, or secrets.
- Maintains an audit event for consent, download, upload confirmation, response, and revocation.

Direct entry of a user's John Deere password into QGIS is prohibited. Long-lived
provider tokens and the Deere application secret are prohibited from QGIS project
files, settings, logs, manifests, HTML reviews, crash reports, and release ZIPs.

### Provider-neutral connector boundary

Future source layout may add:

```text
yield_data_cleaner/
  platforms/
    base.py
    models.py
    receipts.py
    john_deere.py
```

The provider-neutral interface will cover:

- Capability discovery: read operations, read boundaries, download files, upload files, or publish map layers.
- Account/organization, field, season, and operation selection.
- Download into the same immutable local source package used by file importers.
- Mapping remote measurements into the canonical schema with provider IDs and versioned provenance.
- Idempotent additive upload with a client-generated operation key.
- Upload-status polling, readback, conflict handling, and durable receipts.
- Provider-specific terms, scopes, rate limits, data retention, and deletion behavior.

Other equipment platforms may be added only when an authorized public or partner
API, test environment, compatible terms, and representative data are available.

### Send-back safety rules

- The default is local-only; remote upload is opt-in per completed run.
- Download permission never implies upload permission.
- Pull and push scopes are requested separately when the provider permits it.
- The original remote operation and downloaded source package remain unchanged.
- The uploaded artifact is clearly named as cleaned output and includes plugin, recipe, schema, crop, unit, and creation-version metadata where the destination format permits it.
- The user sees the exact artifact and destination before confirmation.
- A failed or unverified upload remains `upload_unconfirmed`; local cleaning success is reported separately.
- Retry uses an idempotency key or remote duplicate check to avoid repeated uploads.
- Send-to-machine or operational-control endpoints are outside this cleaning workflow unless separately designed, reviewed, and approved.

### Post-1.0 delivery phases

#### Phase 9A - Connector foundation and John Deere sandbox read (planned 1.1.x)

- [ ] Confirm John Deere developer application approval, API agreement, access tier, scopes, quotas, and production requirements.
- [ ] Build the provider-neutral connector contracts and local immutable download package.
- [ ] Deploy a minimal secret-holding OAuth integration service with threat model, monitoring, retention, and revocation controls.
- [ ] Connect and disconnect a John Deere sandbox user through the system browser.
- [ ] List only organizations explicitly connected to the application.
- [ ] Select field, season, and harvest Field Operation.
- [ ] Download point-level harvest Shapefile plus Deere metadata and units.
- [ ] Verify EPSG:4326 recognition and transform through the standard CRS workflow.
- [ ] Clean the downloaded operation locally without any write permission.
- [ ] Complete security review of plugin, service, redirect flow, token storage, logs, and data retention.

**Phase 9A exit gate:** an authorized sandbox user can pull a selected harvest operation and clean it locally, while secrets and long-lived tokens remain outside the public plugin.

#### Phase 9B - John Deere production pull (planned 1.2.x)

- [ ] Complete Deere production review and obtain required access.
- [ ] Add pagination, rate-limit handling, retries, cancellation, and expired/revoked authorization handling.
- [ ] Add provider organization/field/operation provenance to the run manifest without exposing tokens.
- [ ] Validate multiple crops, organizations, field operations, units, and point resolutions with consenting test users.
- [ ] Publish privacy, support, deletion, disconnect, and incident-response documentation.
- [ ] Pass QGIS Plugin Repository security review with the connector enabled but no bundled credentials.

**Phase 9B exit gate:** consenting production users can reliably pull selected Deere harvest operations into the local, non-destructive cleaning workflow.

#### Phase 9C - Additive John Deere send-back (planned 1.3.x, conditional)

- [ ] Confirm which cleaned formats Deere will accept and how Operations Center presents each uploaded artifact.
- [ ] Confirm application approval, access tier, write scopes, quotas, and customer permissions.
- [ ] Implement exact upload preview and separate confirmation.
- [ ] Upload only a new clearly named file or contributed map layer; never overwrite the source Field Operation.
- [ ] Poll processing status and read back the resulting resource.
- [ ] Store remote ID, checksum, status, timestamp, user confirmation, and response receipt in the local manifest.
- [ ] Test duplicate prevention, retry, partial failure, rejected format, revoked permission, and readback mismatch.
- [ ] Perform security, privacy, and end-to-end user acceptance review before production enablement.

**Phase 9C exit gate:** a consenting user can explicitly publish a new cleaned artifact to the selected Deere organization and receive verified readback without modifying the original source operation.

## 20. Definition of done for version 1.0.0

Version 1.0.0 is complete only when all of the following are checked:

- [ ] One-field guided workflow is complete.
- [ ] Processing workflow is complete and uses the same engine.
- [ ] Existing, digitized, and derived boundary modes are complete.
- [ ] Outside-boundary observations are excluded non-destructively.
- [ ] Generic point/vector and delimited import are complete.
- [ ] Loaded-layer and browse-from-computer input paths are complete for yield data and existing field boundaries.
- [ ] CRS recognition, user confirmation, axis handling, transformation, provenance, and failure checks are validated.
- [ ] Advertised vendor profiles are validated with representative files.
- [ ] Corn, soybean, and wheat conversions are validated.
- [ ] Imperial and Metric workflows are validated.
- [ ] Pass reconstruction and confidence reporting are validated.
- [ ] Every required filter family is implemented and tested.
- [ ] Recommendation preview and manual overrides are complete.
- [ ] Output package, manifest, recipe, and summaries are complete.
- [ ] Portable HTML review is complete and visually inspected.
- [ ] ADAPT features advertised for 1.0 pass schema and semantic validation.
- [ ] Real-data validation results and known limitations are published.
- [ ] QGIS compatibility matrix passes for claimed versions.
- [ ] Source and the exact packaged ZIP pass Python parse/BOM, security, metadata, archive, dependency, and Qt6/PyQGIS checks without checker crashes or skipped files.
- [ ] GPL licensing and third-party notices are complete.
- [ ] Public documentation and release artifacts are live.
