# Contributing

Thank you for helping improve Yield Data Cleaner.

## Development rules

- Keep original yield-monitor observations immutable and preserve filter provenance.
- Represent missing inputs as unavailable, never as a successful zero value.
- Keep scientific calculations independently testable where practical.
- Add tests for every bug fix and data-format mapping.
- Never commit private farm data, credentials, OAuth tokens, client secrets, or proprietary vendor binaries.
- Use `SPDX-License-Identifier: GPL-3.0-or-later` in distributed Python files.
- Keep plugin, documentation, archive, and Git tag versions synchronized.

## Pull requests

Describe the input format or workflow affected, validation performed, QGIS
versions tested, and any scientific or compatibility limitations. Public test
fixtures must be synthetic or explicitly authorized and sanitized.
