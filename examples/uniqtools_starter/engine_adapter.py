"""Minimal UniqTools-style adapter around the public uniqdiff engine API.

This is an example for future packages such as uniqcheck, uniqrowdiff, and
uniqreport. It keeps product-layer decisions outside uniqdiff and depends only
on documented public imports.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from uniqdiff import CompareResult, compare_files


@dataclass(frozen=True)
class PresenceComparisonRequest:
    """Input contract for a higher-level tool command."""

    first: Path
    second: Path
    key: str
    format: str = "csv"
    mode: str = "auto"
    result_mode: str = "file"
    output: Optional[Path] = None
    temp_dir: Optional[Path] = None


def run_presence_comparison(request: PresenceComparisonRequest) -> CompareResult:
    """Run a key-based presence comparison through the stable uniqdiff API."""

    return compare_files(
        str(request.first),
        str(request.second),
        format=request.format,
        key=request.key,
        mode=request.mode,
        result_mode=request.result_mode,
        output=None if request.output is None else str(request.output),
        temp_dir=None if request.temp_dir is None else str(request.temp_dir),
        include_common=True,
        include_duplicates=True,
    )


def summarize_for_tool(result: CompareResult) -> dict[str, Any]:
    """Return a compact summary that a product-layer tool can render or check."""

    return {
        "only_in_first": result.stats.only_in_first_count,
        "only_in_second": result.stats.only_in_second_count,
        "common": result.stats.common_count,
        "duplicates_first": result.stats.duplicate_first_count,
        "duplicates_second": result.stats.duplicate_second_count,
        "backend": result.metadata.get("backend"),
        "result_mode": result.metadata.get("result_mode"),
        "output": result.metadata.get("output"),
    }


def _write_demo_csv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = ["id", "name", "status"]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(row[column] for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    workspace = Path.cwd() / ".tmp" / "uniqtools_starter"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    try:
        old_csv = workspace / "old.csv"
        new_csv = workspace / "new.csv"
        output = workspace / "presence.jsonl"

        _write_demo_csv(
            old_csv,
            [
                {"id": "1", "name": "Ann", "status": "active"},
                {"id": "2", "name": "Bob", "status": "active"},
                {"id": "2", "name": "Bob", "status": "active"},
            ],
        )
        _write_demo_csv(
            new_csv,
            [
                {"id": "2", "name": "Bob", "status": "inactive"},
                {"id": "3", "name": "Cara", "status": "active"},
            ],
        )

        result = run_presence_comparison(
            PresenceComparisonRequest(
                first=old_csv,
                second=new_csv,
                key="id",
                output=output,
                temp_dir=workspace,
            )
        )

        print(json.dumps(summarize_for_tool(result), indent=2, sort_keys=True))
        print("removed ids:", [row["id"] for row in result.iter_section("only_in_first")])
        print("new ids:", [row["id"] for row in result.iter_section("only_in_second")])
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
