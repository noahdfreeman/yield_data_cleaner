# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, read-only inspection of generic delimited yield files."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .column_detection import MappingSuggestion, detect_columns

MAX_INSPECTION_BYTES = 1_048_576
DEFAULT_SAMPLE_ROWS = 50


@dataclass(frozen=True)
class DelimitedInspection:
    path: str
    encoding: str
    delimiter: str
    columns: tuple[str, ...]
    sample_rows: tuple[dict[str, str], ...]
    mapping_suggestions: tuple[MappingSuggestion, ...]
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mapping_suggestions"] = [item.to_dict() for item in self.mapping_suggestions]
        return payload


def _decode_sample(raw: bytes) -> tuple[str, str]:
    if b"\x00" in raw:
        raise ValueError("The selected file appears to be binary, not delimited text")
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("The selected file encoding could not be recognized")


def _delimiter(text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        counts = {delimiter: first_line.count(delimiter) for delimiter in (",", "\t", ";", "|")}
        choice, count = max(counts.items(), key=lambda item: item[1])
        if count <= 0:
            raise ValueError("No supported delimiter was detected")
        return choice


def inspect_delimited_file(
    path: str | Path, sample_rows: int = DEFAULT_SAMPLE_ROWS
) -> DelimitedInspection:
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError(f"Delimited input does not exist: {source}")
    if sample_rows < 1 or sample_rows > 1000:
        raise ValueError("sample_rows must be between 1 and 1000")
    size = source.stat().st_size
    with source.open("rb") as stream:
        raw = stream.read(MAX_INSPECTION_BYTES)
    text, encoding = _decode_sample(raw)
    delimiter = _delimiter(text)
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    columns = tuple(
        str(column).strip() for column in (reader.fieldnames or ()) if str(column).strip()
    )
    if not columns:
        raise ValueError("The delimited input has no usable header columns")
    if len(set(columns)) != len(columns):
        raise ValueError("The delimited input contains duplicate header columns")
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append(
            {str(key).strip(): "" if value is None else str(value) for key, value in row.items()}
        )
        if len(rows) >= sample_rows:
            break
    suggestions = tuple(detect_columns(columns, rows))
    return DelimitedInspection(
        path=str(source.resolve()),
        encoding=encoding,
        delimiter=delimiter,
        columns=columns,
        sample_rows=tuple(rows),
        mapping_suggestions=suggestions,
        truncated=size > len(raw),
    )
