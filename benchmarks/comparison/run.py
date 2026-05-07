"""Run cross-tool comparison benchmarks.

The suite is intentionally neutral: it reports fit-by-use-case and comparable
measurements, not a universal "winner".
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for import_root in (PROJECT_ROOT, SRC_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from benchmarks.comparison.adapters import BenchmarkAdapter, default_adapters  # noqa: E402
from benchmarks.comparison.data import PROFILES, generate_dataset, profile_defaults  # noqa: E402
from benchmarks.comparison.measure import measure  # noqa: E402
from benchmarks.comparison.models import DatasetPaths, ScenarioResult  # noqa: E402
from benchmarks.comparison.report import write_jsonl, write_markdown  # noqa: E402

SCENARIO_METHODS = {
    "row_presence_by_key": "row_presence",
    "duplicate_detection_by_key": "duplicate_detection",
    "row_level_changed_fields_by_key": "row_level_changed_fields",
    "large_output_handling": "large_output_handling",
    "implementation_setup_complexity": "setup_complexity",
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run fair comparison benchmarks for uniqdiff and adjacent tools."
    )
    parser.add_argument("--rows", type=int, default=10_000, help="Rows per left/right CSV.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic dataset seed.")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="orders",
        help="Concrete workload profile. Explicit ratio/shape flags override profile defaults.",
    )
    parser.add_argument("--overlap-ratio", type=float)
    parser.add_argument("--changed-ratio", type=float)
    parser.add_argument("--duplicate-ratio", type=float)
    parser.add_argument("--null-ratio", type=float)
    parser.add_argument("--payload-bytes", type=int)
    parser.add_argument("--wide-columns", type=int)
    parser.add_argument(
        "--adapter",
        action="append",
        choices=[adapter.name for adapter in default_adapters()],
        help="Adapter to run. May be passed multiple times. Defaults to all adapters.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIO_METHODS),
        help="Scenario to run. May be passed multiple times. Defaults to all scenarios.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "benchmarks" / "results" / "comparison",
        help="Directory for generated data, JSONL results, and Markdown report.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep generated CSV input data after the run.",
    )
    args = parser.parse_args(argv)

    defaults = profile_defaults(args.profile)
    overlap_ratio = _arg_or_default(args.overlap_ratio, defaults["overlap_ratio"])
    changed_ratio = _arg_or_default(args.changed_ratio, defaults["changed_ratio"])
    duplicate_ratio = _arg_or_default(args.duplicate_ratio, defaults["duplicate_ratio"])
    null_ratio = _arg_or_default(args.null_ratio, defaults["null_ratio"])
    payload_bytes = _arg_or_default(args.payload_bytes, defaults["payload_bytes"])
    wide_columns = _arg_or_default(args.wide_columns, defaults["wide_columns"])

    _validate_ratios(parser, overlap_ratio, changed_ratio, duplicate_ratio, null_ratio)
    if args.rows < 0:
        parser.error("--rows must be greater than or equal to zero")
    if payload_bytes < 0:
        parser.error("--payload-bytes must be greater than or equal to zero")
    if wide_columns < 0:
        parser.error("--wide-columns must be greater than or equal to zero")

    output_dir = args.output_dir.resolve()
    data_dir = output_dir / "data"
    adapter_output_dir = output_dir / "adapter-output"
    adapter_output_dir.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset(
        data_dir,
        rows=args.rows,
        overlap_ratio=overlap_ratio,
        changed_ratio=changed_ratio,
        duplicate_ratio=duplicate_ratio,
        seed=args.seed,
        profile=args.profile,
        null_ratio=null_ratio,
        payload_bytes=payload_bytes,
        wide_columns=wide_columns,
    )

    adapters = _select_adapters(args.adapter)
    scenarios = args.scenario or list(SCENARIO_METHODS)
    results = _run_suite(adapters, scenarios, dataset, adapter_output_dir)

    results_path = output_dir / "results.jsonl"
    report_path = output_dir / "report.md"
    write_jsonl(results, results_path)
    write_markdown(results, report_path)

    if not args.keep_data:
        shutil.rmtree(data_dir, ignore_errors=True)

    print(f"Wrote JSONL results: {results_path}")
    print(f"Wrote Markdown report: {report_path}")
    return 0


def _arg_or_default(value: int | float | None, default: int | float) -> int | float:
    return default if value is None else value


def _validate_ratios(parser: argparse.ArgumentParser, *ratios: float) -> None:
    for ratio in ratios:
        if not 0 <= ratio <= 1:
            parser.error("ratio arguments must be between 0.0 and 1.0")


def _select_adapters(names: list[str] | None) -> list[BenchmarkAdapter]:
    adapters = default_adapters()
    if not names:
        return adapters
    selected = set(names)
    return [adapter for adapter in adapters if adapter.name in selected]


def _run_suite(
    adapters: list[BenchmarkAdapter],
    scenarios: list[str],
    dataset: DatasetPaths,
    output_dir: Path,
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for adapter in adapters:
        adapter.warmup()
        adapter_dir = output_dir / adapter.name.replace("/", "-")
        adapter_dir.mkdir(parents=True, exist_ok=True)
        for scenario in scenarios:
            method_name = SCENARIO_METHODS[scenario]
            method = getattr(adapter, method_name)
            results.append(_run_measured(adapter, scenario, method, dataset, adapter_dir))
    return results


def _run_measured(
    adapter: BenchmarkAdapter,
    scenario: str,
    method: Callable[[DatasetPaths, Path], ScenarioResult],
    dataset: DatasetPaths,
    output_dir: Path,
) -> ScenarioResult:
    try:
        measured = measure(lambda: method(dataset, output_dir))
        _annotate_result(measured, dataset)
        return measured
    except Exception as exc:  # pragma: no cover - defensive around optional adapters.
        error_result = ScenarioResult(
            adapter=adapter.name,
            scenario=scenario,
            support_level="not_supported",
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            notes=["Adapter raised an exception; inspect dependency version and adapter notes."],
        )
        _annotate_result(error_result, dataset)
        return error_result


def _annotate_result(result: ScenarioResult, dataset: DatasetPaths) -> None:
    metadata = dataset.metadata
    expected = metadata["expected_counts"]
    result.workload = {
        "profile": metadata["profile"],
        "rows_per_side": metadata["rows_per_side"],
        "seed": metadata["seed"],
        "overlap_ratio": metadata["overlap_ratio"],
        "changed_ratio": metadata["changed_ratio"],
        "duplicate_ratio": metadata["duplicate_ratio"],
        "null_ratio": metadata["null_ratio"],
        "payload_bytes": metadata["payload_bytes"],
        "wide_columns": metadata["wide_columns"],
        "schema_columns": len(metadata["schema_columns"]),
    }
    if result.status == "skipped":
        result.input_rows = 0
        result.rows_per_second = None
        return
    if result.input_rows is None:
        if result.scenario == "duplicate_detection_by_key":
            result.input_rows = expected["duplicate_rows"]
        elif result.scenario == "implementation_setup_complexity":
            result.input_rows = 0
        else:
            result.input_rows = expected["left_rows"] + expected["right_rows"]
    if result.elapsed_seconds and result.input_rows:
        result.rows_per_second = round(result.input_rows / result.elapsed_seconds, 2)
    if result.status == "ok":
        result.extra["expected_counts"] = _expected_for_scenario(result.scenario, expected)
        result.extra["matches_expected"] = _matches_expected(result, expected)


def _expected_for_scenario(scenario: str, expected: dict[str, int]) -> dict[str, int]:
    if scenario in {"row_presence_by_key", "large_output_handling"}:
        return {
            "only_in_left": expected["only_in_left"],
            "only_in_right": expected["only_in_right"],
            "common": expected["common"],
        }
    if scenario == "duplicate_detection_by_key":
        return {"duplicate_count": expected["duplicate_count"]}
    if scenario == "row_level_changed_fields_by_key":
        return {
            "changed_rows": expected["changed_rows"],
            "changed_fields": expected["changed_fields"],
        }
    return {}


def _matches_expected(result: ScenarioResult, expected: dict[str, int]) -> bool | None:
    if result.scenario == "row_presence_by_key":
        return (
            result.only_in_left_count == expected["only_in_left"]
            and result.only_in_right_count == expected["only_in_right"]
            and result.common_count == expected["common"]
        )
    if result.scenario == "duplicate_detection_by_key":
        return result.duplicate_count == expected["duplicate_count"]
    if result.scenario == "row_level_changed_fields_by_key":
        return (
            result.changed_rows_count == expected["changed_rows"]
            and result.changed_fields_count == expected["changed_fields"]
        )
    if result.scenario == "large_output_handling":
        counts = [
            result.only_in_left_count,
            result.only_in_right_count,
            result.common_count,
        ]
        if any(count is None for count in counts):
            return None
        return (
            result.only_in_left_count == expected["only_in_left"]
            and result.only_in_right_count == expected["only_in_right"]
            and result.common_count == expected["common"]
        )
    return None


if __name__ == "__main__":
    raise SystemExit(main())
