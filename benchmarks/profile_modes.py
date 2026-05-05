"""Profile uniqdiff execution modes with cProfile and tracemalloc.

The goal is to find bottlenecks, not to prove that one mode is universally
faster. Dataset generation is deterministic and happens outside the measured
profile window.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import shutil
import sys
import time
import tracemalloc
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from uniqdiff import compare, compare_sorted_iter, write_sorted_diff_file  # noqa: E402

ProfilerTarget = Callable[[], Any]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Profile uniqdiff execution modes.")
    parser.add_argument("--size", "--rows", dest="size", type=int, default=20_000)
    parser.add_argument("--overlap", type=float, default=0.5)
    parser.add_argument("--top", type=int, default=12, help="Functions to include per mode.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=[
            "memory",
            "memory_no_order",
            "sqlite",
            "hash_partition",
            "external_sort",
            "file_result",
            "sorted_stream",
            "sorted_stream_file",
        ],
        help="Scenario to profile. May be passed multiple times. Defaults to all.",
    )
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument("--partition-count", type=int, default=32)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "benchmarks" / "results"))
    args = parser.parse_args(argv)

    if args.size < 0:
        parser.error("--size must be greater than or equal to zero")
    if not 0 <= args.overlap <= 1:
        parser.error("--overlap must be between 0.0 and 1.0")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir / "profile_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    scenarios = args.scenario or [
        "memory",
        "memory_no_order",
        "sqlite",
        "hash_partition",
        "external_sort",
        "file_result",
        "sorted_stream",
        "sorted_stream_file",
    ]
    first, second = _make_inputs(args.size, overlap=args.overlap)

    results: list[dict[str, Any]] = []
    try:
        for scenario in scenarios:
            target = _scenario_target(
                scenario,
                first=first,
                second=second,
                chunk_size=args.chunk_size,
                partition_count=args.partition_count,
                temp_dir=temp_dir,
            )
            results.append(_profile_scenario(scenario, target, top=args.top))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    jsonl_path = output_dir / "profile-results.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")

    report_path = output_dir / "profile-report.md"
    report_path.write_text(_markdown_report(results), encoding="utf-8")
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {report_path}")
    return 0


def _make_inputs(size: int, *, overlap: float) -> tuple[list[int], list[int]]:
    overlap_count = int(size * overlap)
    first = list(range(size))
    second_start = size - overlap_count
    second = list(range(second_start, second_start + size))
    return first, second


def _scenario_target(
    scenario: str,
    *,
    first: list[int],
    second: list[int],
    chunk_size: int,
    partition_count: int,
    temp_dir: Path,
) -> ProfilerTarget:
    if scenario == "memory":

        def run_memory() -> Any:
            return compare(first, second, include_common=True, mode="memory")

        return run_memory

    if scenario == "memory_no_order":

        def run_memory_no_order() -> Any:
            return compare(
                first,
                second,
                include_common=True,
                mode="memory",
                preserve_order=False,
            )

        return run_memory_no_order

    if scenario == "sqlite":

        def run_sqlite() -> Any:
            return compare(
                first,
                second,
                include_common=True,
                mode="disk",
                disk_strategy="sqlite",
                chunk_size=chunk_size,
                temp_dir=str(temp_dir),
            )

        return run_sqlite

    if scenario == "hash_partition":

        def run_hash_partition() -> Any:
            return compare(
                first,
                second,
                include_common=True,
                mode="disk",
                disk_strategy="hash_partition",
                chunk_size=chunk_size,
                partition_count=partition_count,
                temp_dir=str(temp_dir),
            )

        return run_hash_partition

    if scenario == "external_sort":

        def run_external_sort() -> Any:
            return compare(
                first,
                second,
                include_common=True,
                mode="disk",
                disk_strategy="external_sort",
                chunk_size=chunk_size,
                temp_dir=str(temp_dir),
            )

        return run_external_sort

    if scenario == "file_result":

        def run_file_result() -> Any:
            output = temp_dir / "profile-file-result.jsonl"
            output.unlink(missing_ok=True)
            return compare(
                first,
                second,
                include_common=True,
                mode="disk",
                disk_strategy="sqlite",
                result_mode="file",
                output=str(output),
                chunk_size=chunk_size,
                temp_dir=str(temp_dir),
            )

        return run_file_result

    if scenario == "sorted_stream":

        def run_sorted_stream() -> Any:
            return list(compare_sorted_iter(first, second, include_common=True))

        return run_sorted_stream

    if scenario == "sorted_stream_file":

        def run_sorted_stream_file() -> Any:
            output = temp_dir / "profile-sorted-stream.jsonl"
            output.unlink(missing_ok=True)
            return write_sorted_diff_file(first, second, str(output), include_common=True)

        return run_sorted_stream_file

    raise ValueError(f"Unknown scenario: {scenario}")


def _profile_scenario(scenario: str, target: ProfilerTarget, *, top: int) -> dict[str, Any]:
    profiler = cProfile.Profile()
    tracemalloc.start()
    started = time.perf_counter()
    profiler.enable()
    result = target()
    profiler.disable()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stats = pstats.Stats(profiler).strip_dirs().sort_stats("cumulative")
    top_functions = _top_functions(stats, limit=top)
    uniqdiff_functions = [
        item for item in top_functions if "uniqdiff" in item["file"] or item["file"].endswith(".py")
    ][:top]

    return {
        "scenario": scenario,
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_mb": round(peak / 1024 / 1024, 3),
        "result_summary": _result_summary(result),
        "top_functions": top_functions,
        "top_uniqdiff_functions": uniqdiff_functions,
    }


def _top_functions(stats: pstats.Stats, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for func in stats.fcn_list[:limit]:
        ccalls, ncalls, total_time, cumulative_time, _ = stats.stats[func]
        filename, line, name = func
        rows.append(
            {
                "file": filename,
                "line": line,
                "function": name,
                "primitive_calls": ccalls,
                "total_calls": ncalls,
                "total_time_seconds": round(total_time, 6),
                "cumulative_time_seconds": round(cumulative_time, 6),
            }
        )
    return rows


def _result_summary(result: Any) -> dict[str, Any]:
    if isinstance(result, list):
        return {"row_count": len(result)}
    if isinstance(result, int):
        return {"row_count": result}
    stats = getattr(result, "stats", None)
    if stats is None:
        return {"type": type(result).__name__}
    return {
        "only_in_first": stats.only_in_first_count,
        "only_in_second": stats.only_in_second_count,
        "common": stats.common_count,
        "backend": getattr(result, "metadata", {}).get("backend"),
        "result_mode": getattr(result, "metadata", {}).get("result_mode"),
    }


def _markdown_report(results: Iterable[dict[str, Any]]) -> str:
    rows = list(results)
    lines = [
        "# uniqdiff Profiling Report",
        "",
        "This report is generated by `benchmarks/profile_modes.py` using `cProfile` "
        "and `tracemalloc`. Results are workload-dependent and should be used to "
        "find bottlenecks, not as universal performance claims.",
        "",
        "## Summary",
        "",
        "| Scenario | Elapsed, s | Peak MB | Result |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {scenario} | {elapsed_seconds:.6f} | {peak_memory_mb:.3f} | `{summary}` |".format(
                scenario=row["scenario"],
                elapsed_seconds=row["elapsed_seconds"],
                peak_memory_mb=row["peak_memory_mb"],
                summary=json.dumps(row["result_summary"], sort_keys=True),
            )
        )

    for row in rows:
        lines.extend(
            [
                "",
                f"## {row['scenario']}",
                "",
                "| Function | Calls | Total, s | Cumulative, s |",
                "|---|---:|---:|---:|",
            ]
        )
        for item in row["top_functions"]:
            location = f"{item['file']}:{item['line']} `{item['function']}`"
            lines.append(
                "| {location} | {calls} | {total:.6f} | {cumulative:.6f} |".format(
                    location=location,
                    calls=item["total_calls"],
                    total=item["total_time_seconds"],
                    cumulative=item["cumulative_time_seconds"],
                )
            )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
