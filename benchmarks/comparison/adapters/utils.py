"""Shared adapter utilities."""

from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path


def has_module(name: str) -> bool:
    """Return whether a module can be imported."""

    return importlib.util.find_spec(name) is not None


def read_csv_rows(path: str) -> list[dict[str, str]]:
    """Read CSV rows as dictionaries."""

    with Path(path).open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> int:
    """Write rows to JSONL and return output size."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            file.write("\n")
    return path.stat().st_size


def row_presence_counts(left: list[dict[str, str]], right: list[dict[str, str]]) -> dict[str, int]:
    """Compute row presence counts by `id`."""

    left_keys = {row["id"] for row in left}
    right_keys = {row["id"] for row in right}
    return {
        "only_in_left": len(left_keys - right_keys),
        "only_in_right": len(right_keys - left_keys),
        "common": len(left_keys & right_keys),
    }


def duplicate_count(rows: list[dict[str, str]]) -> int:
    """Count duplicate entries by `id`, excluding the first occurrence."""

    counts = Counter(row["id"] for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def changed_rows(left: list[dict[str, str]], right: list[dict[str, str]]) -> tuple[int, int]:
    """Count changed rows and changed fields for common keys."""

    left_by_key = {row["id"]: row for row in left}
    right_by_key = {row["id"]: row for row in right}
    changed_row_count = 0
    changed_field_count = 0
    ignored = {"id", "source"}
    for key in sorted(left_by_key.keys() & right_by_key.keys()):
        field_changes = sum(
            1
            for field, left_value in left_by_key[key].items()
            if field not in ignored and left_value != right_by_key[key].get(field)
        )
        if field_changes:
            changed_row_count += 1
            changed_field_count += field_changes
    return changed_row_count, changed_field_count


def diff_rows_for_large_output(
    left: list[dict[str, str]],
    right: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Return row-presence diff rows for file-output scenarios."""

    left_by_key = {row["id"]: row for row in left}
    right_by_key = {row["id"]: row for row in right}
    rows: list[dict[str, object]] = []
    for key in sorted(left_by_key.keys() - right_by_key.keys()):
        rows.append({"section": "only_in_left", "value": left_by_key[key]})
    for key in sorted(right_by_key.keys() - left_by_key.keys()):
        rows.append({"section": "only_in_right", "value": right_by_key[key]})
    return rows
