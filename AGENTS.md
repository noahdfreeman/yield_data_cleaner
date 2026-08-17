# Agent instructions

## QGIS testing ownership

- Do not launch, control, reload, or interact with QGIS to test this project.
- Do not run QGIS desktop or headless QGIS smoke tests unless Noah explicitly
  authorizes that specific test run.
- Noah performs all QGIS testing and reports the results.
- Agents may run non-QGIS checks such as pure-Python unit tests, static analysis,
  formatting, packaging, archive validation, and release-version verification.

## Version updates and QGIS live reloading

- Ensure all source updates are live in the QGIS development link so Noah can reload the plugin via QGIS Plugin Reloader and use it immediately.
- Every new improvement or feature update must increment and synchronize the plugin version number across `yield_data_cleaner/metadata.txt`, `yield_data_cleaner/version.py`, and `CHANGELOG.md`.
- After every improvement, explicitly state the updated version number to the user.

