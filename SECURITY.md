# Security policy

## Supported versions

Yield Data Cleaner is experimental. Security fixes are applied to the current
development branch and the most recent published version.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability that could expose user
data or credentials. Use GitHub's private vulnerability reporting for
`noahdfreeman/yield_data_cleaner` when enabled, or contact the repository owner
through the email in the packaged `metadata.txt`.

Please include the affected version, a concise reproduction, impact, and any
suggested remediation. Do not include private yield datasets, farm locations, or
equipment-platform tokens.

## Security properties

- Core processing is local and does not upload yield data.
- Input files are read without modification.
- Output paths are user-selected and completed runs are not silently overwritten.
- Release archives contain no compiled binaries, legacy OCX files, credentials,
  or private farm fixtures.
- Mapping profiles are bounded UTF-8 JSON and are treated as data, not executable
  configuration.
- Future equipment-platform OAuth tokens will not be embedded in the plugin or
  committed to the repository.

Every release candidate must pass the exact ZIP validator, Bandit, and
detect-secrets checks before it is considered ready for the QGIS Plugin
Repository. The repository's own asynchronous security scan remains the
authoritative publication result.
