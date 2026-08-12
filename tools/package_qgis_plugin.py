# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a deterministic installable plugin ZIP from the public package."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "yield_data_cleaner"
METADATA = PACKAGE / "metadata.txt"

EXCLUDED_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak"}


def metadata_version() -> str:
    text = METADATA.read_text(encoding="utf-8")
    match = re.search(r"(?m)^version=([0-9]+\.[0-9]+\.[0-9]+)\s*$", text)
    if not match:
        raise SystemExit("metadata.txt has no semantic version")
    return match.group(1)


def included_files():
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PACKAGE)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path, Path(PACKAGE.name) / relative


def main() -> Path:
    version = metadata_version()
    destination = ROOT / "dist" / f"yield_data_cleaner-{version}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for source, member in included_files():
            info = zipfile.ZipInfo(member.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    print(destination)
    return destination


if __name__ == "__main__":
    main()
