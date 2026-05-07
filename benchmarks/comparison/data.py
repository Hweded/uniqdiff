"""Deterministic, domain-shaped CSV dataset generator for cross-tool benchmarks."""

from __future__ import annotations

import csv
import json
import random
import shutil
from pathlib import Path
from typing import Any

from benchmarks.comparison.models import DatasetPaths

PROFILES: dict[str, dict[str, Any]] = {
    "orders": {
        "description": "Order-like rows with mixed string/numeric/date columns.",
        "overlap_ratio": 0.70,
        "changed_ratio": 0.20,
        "duplicate_ratio": 0.05,
        "null_ratio": 0.03,
        "payload_bytes": 24,
        "wide_columns": 0,
    },
    "wide_orders": {
        "description": "Order-like rows plus extra metric columns to stress row width.",
        "overlap_ratio": 0.75,
        "changed_ratio": 0.15,
        "duplicate_ratio": 0.03,
        "null_ratio": 0.05,
        "payload_bytes": 64,
        "wide_columns": 20,
    },
    "large_output": {
        "description": "Lower overlap to create a large only-left/only-right output.",
        "overlap_ratio": 0.20,
        "changed_ratio": 0.10,
        "duplicate_ratio": 0.02,
        "null_ratio": 0.02,
        "payload_bytes": 96,
        "wide_columns": 4,
    },
}

BASE_COLUMNS = [
    "id",
    "account_id",
    "region",
    "status",
    "amount_cents",
    "discount_pct",
    "updated_at",
    "email",
    "nullable_note",
    "payload",
    "source",
]
DEFAULT_COMPARED_COLUMNS = [
    "account_id",
    "region",
    "status",
    "amount_cents",
    "discount_pct",
    "updated_at",
    "email",
    "nullable_note",
    "payload",
]
CHANGED_COLUMNS = ["status", "amount_cents", "updated_at"]


def profile_defaults(profile: str) -> dict[str, Any]:
    """Return benchmark profile defaults."""

    try:
        return dict(PROFILES[profile])
    except KeyError as exc:
        raise ValueError(f"unknown benchmark profile: {profile}") from exc


def generate_dataset(
    output_dir: Path,
    *,
    rows: int,
    overlap_ratio: float,
    changed_ratio: float,
    duplicate_ratio: float,
    seed: int,
    profile: str = "orders",
    null_ratio: float = 0.03,
    payload_bytes: int = 24,
    wide_columns: int = 0,
) -> DatasetPaths:
    """Generate deterministic left/right CSV files and a duplicate-focused CSV.

    The generated workload is intentionally concrete: order-like records with
    mixed column types, nullable-looking values, and optional wide metric columns.
    Exact expected counts are written to metadata so adapters can be checked for
    correctness, not only timed.
    """

    _validate(rows, overlap_ratio, changed_ratio, duplicate_ratio, null_ratio, payload_bytes)
    if wide_columns < 0:
        raise ValueError("wide_columns must be greater than or equal to zero")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    overlap_count = int(rows * overlap_ratio)
    changed_count = int(overlap_count * changed_ratio)
    duplicate_count = int(rows * duplicate_ratio)

    left_ids = list(range(rows))
    common_ids = left_ids[:overlap_count]
    right_only_ids = list(range(rows, rows + rows - overlap_count))
    right_ids = [*common_ids, *right_only_ids]
    changed_ids = set(rng.sample(common_ids, k=changed_count)) if changed_count else set()

    wide_names = [f"metric_{index:02d}" for index in range(wide_columns)]
    fieldnames = [*BASE_COLUMNS, *wide_names]
    compared_columns = [*DEFAULT_COMPARED_COLUMNS, *wide_names]

    left_path = output_dir / "left.csv"
    right_path = output_dir / "right.csv"
    duplicate_path = output_dir / "duplicates.csv"
    metadata_path = output_dir / "metadata.json"

    left_rows = [
        _row_for(
            row_id,
            side="left",
            changed=False,
            null_ratio=null_ratio,
            payload_bytes=payload_bytes,
            wide_names=wide_names,
        )
        for row_id in left_ids
    ]
    right_rows = [
        _row_for(
            row_id,
            side="right",
            changed=row_id in changed_ids,
            null_ratio=null_ratio,
            payload_bytes=payload_bytes,
            wide_names=wide_names,
        )
        for row_id in right_ids
    ]
    duplicate_rows = [
        _row_for(
            row_id,
            side="dupes",
            changed=False,
            null_ratio=null_ratio,
            payload_bytes=payload_bytes,
            wide_names=wide_names,
        )
        for row_id in left_ids
    ]
    for index in range(duplicate_count):
        row_id = left_ids[index % len(left_ids)] if left_ids else index
        duplicate_rows.append(
            _row_for(
                row_id,
                side="dupes",
                changed=True,
                null_ratio=null_ratio,
                payload_bytes=payload_bytes,
                wide_names=wide_names,
            )
        )

    _write_rows(left_path, left_rows, fieldnames=fieldnames)
    _write_rows(right_path, right_rows, fieldnames=fieldnames)
    _write_rows(duplicate_path, duplicate_rows, fieldnames=fieldnames)

    metadata: dict[str, Any] = {
        "profile": profile,
        "profile_description": PROFILES.get(profile, {}).get("description", "custom workload"),
        "rows_per_side": rows,
        "seed": seed,
        "overlap_ratio": overlap_ratio,
        "changed_ratio": changed_ratio,
        "duplicate_ratio": duplicate_ratio,
        "null_ratio": null_ratio,
        "payload_bytes": payload_bytes,
        "wide_columns": wide_columns,
        "key_column": "id",
        "schema_columns": fieldnames,
        "compared_columns": compared_columns,
        "changed_columns": CHANGED_COLUMNS,
        "expected_counts": {
            "left_rows": len(left_rows),
            "right_rows": len(right_rows),
            "duplicate_rows": len(duplicate_rows),
            "only_in_left": rows - overlap_count,
            "only_in_right": rows - overlap_count,
            "common": overlap_count,
            "duplicate_count": duplicate_count,
            "changed_rows": changed_count,
            "changed_fields": changed_count * len(CHANGED_COLUMNS),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return DatasetPaths(
        left_csv=str(left_path),
        right_csv=str(right_path),
        duplicate_csv=str(duplicate_path),
        metadata_json=str(metadata_path),
        metadata=metadata,
    )


def _validate(
    rows: int,
    overlap_ratio: float,
    changed_ratio: float,
    duplicate_ratio: float,
    null_ratio: float,
    payload_bytes: int,
) -> None:
    if rows < 0:
        raise ValueError("rows must be greater than or equal to zero")
    for name, ratio in {
        "overlap_ratio": overlap_ratio,
        "changed_ratio": changed_ratio,
        "duplicate_ratio": duplicate_ratio,
        "null_ratio": null_ratio,
    }.items():
        if not 0 <= ratio <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if payload_bytes < 0:
        raise ValueError("payload_bytes must be greater than or equal to zero")


def _row_for(
    row_id: int,
    *,
    side: str,
    changed: bool,
    null_ratio: float,
    payload_bytes: int,
    wide_names: list[str],
) -> dict[str, str]:
    amount = (row_id * 17) % 1_000_000
    status = "active" if row_id % 5 else "paused"
    updated_day = (row_id % 28) + 1
    if changed:
        amount += 9_900
        status = "refunded" if row_id % 2 else "manual_review"
        updated_day = ((updated_day + 7 - 1) % 28) + 1

    row = {
        "id": str(row_id),
        "account_id": f"acct-{row_id % 1000:04d}",
        "region": ["na", "eu", "apac", "latam"][row_id % 4],
        "status": status,
        "amount_cents": str(amount),
        "discount_pct": str(row_id % 30),
        "updated_at": f"2026-05-{updated_day:02d}T12:00:00Z",
        "email": f"user{row_id % 100_000}@example.com",
        "nullable_note": "" if _is_nullish(row_id, null_ratio) else f"note-{row_id % 19}",
        "payload": _payload(row_id, payload_bytes),
        "source": "orders" if side in {"left", "right"} else side,
    }
    for index, name in enumerate(wide_names):
        row[name] = str((row_id * (index + 3)) % 100_003)
    return row


def _is_nullish(row_id: int, ratio: float) -> bool:
    if ratio <= 0:
        return False
    threshold = int(ratio * 10_000)
    return ((row_id * 1_103_515_245 + 12_345) & 0x7FFFFFFF) % 10_000 < threshold


def _payload(row_id: int, length: int) -> str:
    if length <= 0:
        return ""
    token = f"payload-{row_id}-"
    repeats = (length // len(token)) + 1
    return (token * repeats)[:length]


def _write_rows(path: Path, rows: list[dict[str, str]], *, fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
