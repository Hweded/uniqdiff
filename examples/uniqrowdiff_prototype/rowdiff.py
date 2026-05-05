"""Prototype for a future uniqrowdiff package built on top of uniqdiff.

The prototype intentionally uses only public uniqdiff imports. Row-level changed
field detection is product-layer behavior and should remain outside the
`uniqdiff` comparison engine.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from uniqdiff import CompareResult, compare_files


@dataclass(frozen=True)
class FieldChange:
    """One changed field for one matched key."""

    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class RowChange:
    """All changed fields for one matched key."""

    key: str
    changes: list[FieldChange]


@dataclass(frozen=True)
class RowDiffSummary:
    """Compact summary suitable for CLI output or CI checks."""

    only_in_first: int
    only_in_second: int
    common: int
    duplicates_first: int
    duplicates_second: int
    changed_rows: int
    changed_fields: int
    skipped_duplicate_keys: int
    backend: Optional[str]
    output: Optional[str]


@dataclass(frozen=True)
class RowDiffResult:
    """Product-layer result that wraps engine facts and row-level changes."""

    engine_result: CompareResult
    summary: RowDiffSummary
    changes: list[RowChange]


def diff_csv_by_key(
    first: Path,
    second: Path,
    *,
    key: str,
    ignore_fields: Iterable[str] = (),
    output: Optional[Path] = None,
) -> RowDiffResult:
    """Compare two CSV files and report field changes for shared unique keys."""

    engine_output = None if output is None else output.with_suffix(".presence.jsonl")
    engine_result = compare_files(
        str(first),
        str(second),
        format="csv",
        key=key,
        mode="auto",
        result_mode="file" if engine_output is not None else "memory",
        output=None if engine_output is None else str(engine_output),
        include_common=True,
        include_duplicates=True,
    )

    first_rows = _index_csv(first, key=key)
    second_rows = _index_csv(second, key=key)
    ignored = {key, *set(ignore_fields)}

    changes: list[RowChange] = []
    skipped_duplicate_keys = 0
    for row_key in sorted(set(first_rows) & set(second_rows)):
        left_matches = first_rows[row_key]
        right_matches = second_rows[row_key]
        if len(left_matches) != 1 or len(right_matches) != 1:
            skipped_duplicate_keys += 1
            continue

        changed_fields = _changed_fields(
            left_matches[0],
            right_matches[0],
            ignore_fields=ignored,
        )
        if changed_fields:
            changes.append(RowChange(key=row_key, changes=changed_fields))

    if output is not None:
        _write_changes_jsonl(output, changes)

    summary = RowDiffSummary(
        only_in_first=engine_result.stats.only_in_first_count,
        only_in_second=engine_result.stats.only_in_second_count,
        common=engine_result.stats.common_count,
        duplicates_first=engine_result.stats.duplicate_first_count,
        duplicates_second=engine_result.stats.duplicate_second_count,
        changed_rows=len(changes),
        changed_fields=sum(len(change.changes) for change in changes),
        skipped_duplicate_keys=skipped_duplicate_keys,
        backend=engine_result.metadata.get("backend"),
        output=None if output is None else str(output),
    )
    return RowDiffResult(engine_result=engine_result, summary=summary, changes=changes)


def _index_csv(path: Path, *, key: str) -> dict[str, list[dict[str, str]]]:
    rows_by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or key not in reader.fieldnames:
            raise ValueError(f"CSV file {path!s} does not contain key column {key!r}")
        for row in reader:
            rows_by_key[row[key]].append(dict(row))
    return dict(rows_by_key)


def _changed_fields(
    before: dict[str, str],
    after: dict[str, str],
    *,
    ignore_fields: set[str],
) -> list[FieldChange]:
    changes: list[FieldChange] = []
    for field in sorted((set(before) | set(after)) - ignore_fields):
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            changes.append(FieldChange(field=field, before=before_value, after=after_value))
    return changes


def _write_changes_jsonl(path: Path, changes: list[RowChange]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        for change in changes:
            file.write(json.dumps({"section": "changed", "value": asdict(change)}) + "\n")


def _write_demo_csv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = ["id", "name", "status", "score", "updated_at"]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(row[column] for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    workspace = Path.cwd() / ".tmp" / "uniqrowdiff_prototype"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    try:
        old_csv = workspace / "old.csv"
        new_csv = workspace / "new.csv"
        output = workspace / "rowdiff.jsonl"

        _write_demo_csv(
            old_csv,
            [
                {
                    "id": "1",
                    "name": "Ann",
                    "status": "active",
                    "score": "10",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "active",
                    "score": "20",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "active",
                    "score": "20",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "4",
                    "name": "Dana",
                    "status": "active",
                    "score": "40",
                    "updated_at": "2026-05-01",
                },
            ],
        )
        _write_demo_csv(
            new_csv,
            [
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "inactive",
                    "score": "25",
                    "updated_at": "2026-05-05",
                },
                {
                    "id": "3",
                    "name": "Cara",
                    "status": "active",
                    "score": "30",
                    "updated_at": "2026-05-05",
                },
                {
                    "id": "4",
                    "name": "Dana",
                    "status": "inactive",
                    "score": "41",
                    "updated_at": "2026-05-05",
                },
            ],
        )

        result = diff_csv_by_key(
            old_csv,
            new_csv,
            key="id",
            ignore_fields=("updated_at",),
            output=output,
        )

        print(json.dumps(asdict(result.summary), indent=2, sort_keys=True))
        for change in result.changes:
            print(json.dumps(asdict(change), sort_keys=True))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
