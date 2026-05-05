"""Run reproducible uniqdiff benchmarks.

The script intentionally uses only the Python standard library so it can run in CI
and fresh development environments.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from uniqdiff import compare  # noqa: E402


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run uniqdiff benchmark scenarios.")
    parser.add_argument("--size", type=int, default=100_000, help="Number of values per input.")
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.5,
        help="Share of the second input that overlaps the first input, from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--data-shape",
        default="int",
        choices=["int", "dict"],
        help="Input item shape to benchmark.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=[
            "memory",
            "auto_memory",
            "auto_disk",
            "sqlite",
            "hash_partition",
            "external_sort",
            "file_result",
        ],
        help="Scenario to run. May be passed multiple times. Defaults to all scenarios.",
    )
    parser.add_argument("--chunk-size", type=int, default=50_000)
    parser.add_argument("--partition-count", type=int, default=64)
    parser.add_argument("--temp-dir", default=str(PROJECT_ROOT / "benchmarks_tmp"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args(argv)

    if args.size < 0:
        parser.error("--size must be greater than or equal to zero")
    if not 0 <= args.overlap <= 1:
        parser.error("--overlap must be between 0.0 and 1.0")

    scenarios = args.scenario or [
        "memory",
        "auto_memory",
        "auto_disk",
        "sqlite",
        "hash_partition",
        "external_sort",
        "file_result",
    ]
    overlap_count = int(args.size * args.overlap)

    temp_root = Path(args.temp_dir)
    temp_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    temp_path = temp_root
    try:
        for scenario in scenarios:
            results.append(
                _run_scenario(
                    scenario,
                    size=args.size,
                    overlap_count=overlap_count,
                    data_shape=args.data_shape,
                    chunk_size=args.chunk_size,
                    partition_count=args.partition_count,
                    temp_dir=temp_path,
                )
            )
    finally:
        _cleanup_benchmark_files(temp_path)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        _print_table(results)
    if args.output:
        Path(args.output).write_text(
            json.dumps(results, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0


def _run_scenario(
    scenario: str,
    *,
    size: int,
    overlap_count: int,
    data_shape: str,
    chunk_size: int,
    partition_count: int,
    temp_dir: Path,
) -> dict[str, Any]:
    first, second = _make_inputs(size, overlap_count, data_shape=data_shape)

    kwargs: dict[str, Any] = {
        "include_common": True,
        "chunk_size": chunk_size,
    }
    if data_shape == "dict":
        kwargs["key"] = "id"

    if scenario == "auto_memory":
        kwargs.update({"mode": "auto", "memory_limit": "1GB"})
    elif scenario == "auto_disk":
        kwargs.update({"mode": "auto", "memory_limit": "1B"})
    elif scenario == "sqlite":
        kwargs.update({"mode": "disk", "disk_strategy": "sqlite", "temp_dir": str(temp_dir)})
    elif scenario == "hash_partition":
        kwargs.update(
            {
                "mode": "disk",
                "disk_strategy": "hash_partition",
                "partition_count": partition_count,
                "temp_dir": str(temp_dir),
            }
        )
    elif scenario == "external_sort":
        kwargs.update({"mode": "disk", "disk_strategy": "external_sort", "temp_dir": str(temp_dir)})
    elif scenario == "file_result":
        kwargs.update(
            {
                "mode": "disk",
                "disk_strategy": "sqlite",
                "result_mode": "file",
                "output": str(temp_dir / f"result-{scenario}.jsonl"),
                "temp_dir": str(temp_dir),
            }
        )
    else:
        kwargs.update({"mode": "memory"})

    tracemalloc.start()
    started = time.perf_counter()
    result = compare(first, second, **kwargs)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_input_items = size * 2
    throughput = total_input_items / elapsed if elapsed else 0.0
    output_size = 0
    output = result.metadata.get("output")
    if output:
        output_size = Path(output).stat().st_size

    return {
        "scenario": scenario,
        "backend": result.metadata.get("backend"),
        "data_shape": data_shape,
        "size": size,
        "overlap_count": overlap_count,
        "chunk_size": chunk_size,
        "partition_count": partition_count if scenario == "hash_partition" else None,
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_bytes": peak,
        "peak_memory_mb": round(peak / 1024 / 1024, 3),
        "items_per_second": round(throughput, 2),
        "only_in_first_count": result.stats.only_in_first_count,
        "only_in_second_count": result.stats.only_in_second_count,
        "common_count": result.stats.common_count,
        "output_bytes": output_size,
        "output_mb": round(output_size / 1024 / 1024, 3),
        "auto_decision": result.metadata.get("auto_decision"),
    }


def _make_inputs(size: int, overlap_count: int, *, data_shape: str) -> tuple[list[Any], list[Any]]:
    first = list(range(size))
    second_start = size - overlap_count
    second = list(range(second_start, second_start + size))
    if data_shape == "dict":
        return _dict_rows(first), _dict_rows(second)
    return first, second


def _dict_rows(values: Iterable[int]) -> list[dict[str, Any]]:
    return [{"id": value, "payload": f"value-{value}"} for value in values]


def _print_table(results: Iterable[dict[str, Any]]) -> None:
    rows = list(results)
    headers = [
        "scenario",
        "backend",
        "data_shape",
        "elapsed_seconds",
        "peak_memory_mb",
        "items_per_second",
        "only_in_first_count",
        "only_in_second_count",
        "common_count",
        "output_mb",
    ]
    widths = {
        header: max(len(header), *(len(str(row[header])) for row in rows))
        for header in headers
    }
    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print("-+-".join("-" * widths[header] for header in headers))
    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def _cleanup_benchmark_files(path: Path) -> None:
    for pattern in ("uniqdiff-*", "result*.jsonl"):
        for item in path.glob(pattern):
            if item.is_file():
                _unlink_best_effort(item)


def _unlink_best_effort(path: Path) -> None:
    for _ in range(3):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
