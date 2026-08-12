# Yield Data Cleaner

Experimental QGIS plugin for inspecting and preparing combine yield-monitor
point data one field at a time.

Version 0.1.0 can:

- inspect a loaded QGIS point layer or a browsed CSV/vector file;
- suggest and review vendor-neutral column mappings;
- save and reload mapping profiles;
- recognize or require confirmation of the source CRS;
- transform geographic points into a local projected analysis CRS; and
- create a non-destructive canonical audit layer with original and normalized
  values;
- validate a single existing boundary or derive a reviewed operational extent;
  and
- classify points inside/outside a boundary while retaining all observations.

No cleaning decision is made by this development version. Canonical records use
`clean_status=unavailable` until versioned filters are implemented and reviewed.

Project documentation and issue tracking:
<https://github.com/noahdfreeman/yield_data_cleaner>
