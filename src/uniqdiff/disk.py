"""Disk output helpers.

This module intentionally starts small. Future versions will host external sorting,
hash partitioning, and disk-backed indexes.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Union

from uniqdiff.exceptions import UnsupportedFormatError
from uniqdiff.result import CompareResult

RESULT_SECTIONS = (
    "only_in_first",
    "only_in_second",
    "common",
    "duplicates_first",
    "duplicates_second",
)


def atomic_write_result(result: CompareResult, output: Union[str, os.PathLike[str]]) -> Path:
    """Write a comparison result atomically based on the output suffix."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()

    fd, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=str(output_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        if suffix == ".json":
            temp_path.write_text(
                json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        elif suffix == ".jsonl":
            _write_jsonl(result, temp_path)
        elif suffix == ".csv":
            _write_csv(result, temp_path)
        else:
            raise UnsupportedFormatError("Output file must have .json, .jsonl, or .csv suffix")
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return output_path


def _write_jsonl(result: CompareResult, path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for section in RESULT_SECTIONS:
            values = getattr(result, section)
            if not values:
                continue
            for value in values:
                file.write(
                    json.dumps(
                        {"section": section, "value": value},
                        ensure_ascii=False,
                        default=str,
                    )
                )
                file.write("\n")


def _write_csv(result: CompareResult, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["section", "value"])
        writer.writeheader()
        for section in RESULT_SECTIONS:
            values = getattr(result, section)
            if not values:
                continue
            for value in values:
                writer.writerow(
                    {
                        "section": section,
                        "value": json.dumps(value, ensure_ascii=False, default=str),
                    }
                )
