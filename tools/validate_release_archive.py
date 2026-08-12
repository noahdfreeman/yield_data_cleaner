# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect the exact QGIS plugin ZIP for structure and parse safety."""

from __future__ import annotations

import ast
import configparser
import io
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

EXPECTED_ROOT = "yield_data_cleaner"
REQUIRED = {
    f"{EXPECTED_ROOT}/__init__.py",
    f"{EXPECTED_ROOT}/metadata.txt",
    f"{EXPECTED_ROOT}/plugin.py",
    f"{EXPECTED_ROOT}/provider.py",
    f"{EXPECTED_ROOT}/LICENSE",
    f"{EXPECTED_ROOT}/README.md",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".dll", ".exe", ".ocx", ".pdb"}
FORBIDDEN_NAMES = {".env", "credentials.json", "secrets.json"}
REQUIRED_METADATA = {
    "name",
    "description",
    "version",
    "qgisMinimumVersion",
    "author",
    "email",
    "about",
    "repository",
}
URL_METADATA = {"homepage", "repository", "tracker"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_release_archive.py <plugin.zip>")
    archive_path = Path(sys.argv[1])
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        missing = sorted(REQUIRED - set(names))
        if missing:
            raise SystemExit(f"Missing required archive members: {missing}")
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts:
                raise SystemExit(f"Unsafe archive path: {name}")
            if not member.parts or member.parts[0] != EXPECTED_ROOT:
                raise SystemExit(f"Unexpected archive root: {name}")
            if "__pycache__" in member.parts or member.suffix.lower() in FORBIDDEN_SUFFIXES:
                raise SystemExit(f"Forbidden release artifact: {name}")
            if member.name.lower() in FORBIDDEN_NAMES:
                raise SystemExit(f"Possible credential file in archive: {name}")
            if member.suffix.lower() == ".py":
                raw = archive.read(name)
                if raw.startswith(b"\xef\xbb\xbf"):
                    raise SystemExit(f"UTF-8 BOM in Python source: {name}")
                ast.parse(raw.decode("utf-8"), filename=name)
        metadata_name = f"{EXPECTED_ROOT}/metadata.txt"
        parser = configparser.ConfigParser()
        metadata_text = archive.read(metadata_name).decode("utf-8-sig")
        parser.read_file(io.StringIO(metadata_text))
        if not parser.has_section("general"):
            raise SystemExit("metadata.txt has no [general] section")
        metadata = parser["general"]
        missing_metadata = sorted(
            key for key in REQUIRED_METADATA if not metadata.get(key, "").strip()
        )
        if missing_metadata:
            raise SystemExit(f"Missing required metadata: {missing_metadata}")
        if not re.fullmatch(r"[A-Za-z_-][A-Za-z0-9_-]*", EXPECTED_ROOT):
            raise SystemExit(f"Invalid plugin folder name: {EXPECTED_ROOT}")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", metadata.get("version", "")):
            raise SystemExit("metadata version is not semantic MAJOR.MINOR.PATCH")
        for key in URL_METADATA:
            value = metadata.get(key, "").strip()
            if value and not value.startswith("https://"):
                raise SystemExit(f"Metadata {key} must use HTTPS")
        icon = metadata.get("icon", "").strip()
        if not icon or f"{EXPECTED_ROOT}/{icon}" not in names:
            raise SystemExit("metadata icon is missing from the archive")
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"ZIP integrity failure: {bad}")
    print(f"Release archive valid: {archive_path}")


if __name__ == "__main__":
    main()
