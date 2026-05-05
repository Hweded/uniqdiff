"""Deterministic CSV dataset generator for cross-tool benchmarks."""

from __future__ import annotations

import csv
import random
import shutil
from pathlib import Path

from benchmarks.comparison.models import DatasetPaths


def generate_dataset(
    output_dir: Path,
    *,
    rows: int,
    overlap_ratio: float,
    changed_ratio: float,
    duplicate_ratio: float,
    seed: int,
) -> DatasetPaths:
    """Generate deterministic left/right CSV files and a duplicate-focused CSV."""

    if rows < 0:
        raise ValueError("rows must be greater than or equal to zero")
    if not 0 <= overlap_ratio <= 1:
        raise ValueError("overlap_ratio must be between 0 and 1")
    if not 0 <= changed_ratio <= 1:
        raise ValueError("changed_ratio must be between 0 and 1")
    if not 0 <= duplicate_ratio <= 1:
        raise ValueError("duplicate_ratio must be between 0 and 1")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    overlap_count = int(rows * overlap_ratio)
    changed_count = int(overlap_count * changed_ratio)
    duplicate_count = int(rows * duplicate_ratio)

    left_ids = list(range(rows))
    right_unique_start = rows
    common_ids = left_ids[:overlap_count]
    right_only_ids = list(range(right_unique_start, right_unique_start + rows - overlap_count))
    right_ids = [*common_ids, *right_only_ids]

    changed_ids = set(rng.sample(common_ids, k=changed_count)) if changed_count else set()

    left_path = output_dir / "left.csv"
    right_path = output_dir / "right.csv"
    duplicate_path = output_dir / "duplicates.csv"

    _write_rows(left_path, [_row_for(row_id, side="left", changed=False) for row_id in left_ids])
    _write_rows(
        right_path,
        [
            _row_for(row_id, side="right", changed=row_id in changed_ids)
            for row_id in right_ids
        ],
    )

    duplicate_rows = [_row_for(row_id, side="dupes", changed=False) for row_id in left_ids]
    for index in range(duplicate_count):
        row_id = left_ids[index % len(left_ids)] if left_ids else index
        duplicate_rows.append(_row_for(row_id, side="dupes", changed=True))
    _write_rows(duplicate_path, duplicate_rows)

    return DatasetPaths(
        left_csv=str(left_path),
        right_csv=str(right_path),
        duplicate_csv=str(duplicate_path),
    )


def _row_for(row_id: int, *, side: str, changed: bool) -> dict[str, str]:
    name = f"name-{row_id}"
    amount = str((row_id * 17) % 10_000)
    status = "active" if row_id % 3 else "paused"
    if changed:
        amount = str(((row_id * 17) + 5) % 10_000)
        status = "changed"
    return {
        "id": str(row_id),
        "name": name,
        "amount": amount,
        "status": status,
        "source": side,
    }


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["id", "name", "amount", "status", "source"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
