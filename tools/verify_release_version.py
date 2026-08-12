# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify synchronized public versions and optional Git tag."""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "yield_data_cleaner"


def main() -> None:
    parser = configparser.ConfigParser()
    parser.read(PACKAGE / "metadata.txt", encoding="utf-8")
    version = parser.get("general", "version", fallback="").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"Invalid metadata version: {version!r}")
    namespace: dict[str, object] = {}
    exec((PACKAGE / "version.py").read_text(encoding="utf-8"), namespace)
    if namespace.get("VERSION") != version:
        raise SystemExit(f"version.py {namespace.get('VERSION')} != metadata {version}")
    for path in (ROOT / "README.md", ROOT / "CHANGELOG.md"):
        if version not in path.read_text(encoding="utf-8"):
            raise SystemExit(f"{path.name} does not mention {version}")
    if len(sys.argv) > 1:
        requested = sys.argv[1].removeprefix("v")
        if requested != version:
            raise SystemExit(f"tag {requested} != metadata {version}")
    print(f"Release versions agree: {version}")


if __name__ == "__main__":
    main()
