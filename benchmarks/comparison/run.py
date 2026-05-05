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
from benchmarks.comparison.data import generate_dataset  # noqa: E402
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
    parser.add_argument("--overlap-ratio", type=float, default=0.7)
    parser.add_argument("--changed-ratio", type=float, default=0.2)
    parser.add_argument("--duplicate-ratio", type=float, default=0.1)
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

    _validate_ratios(parser, args.overlap_ratio, args.changed_ratio, args.duplicate_ratio)
    if args.rows < 0:
        parser.error("--rows must be greater than or equal to zero")

    output_dir = args.output_dir.resolve()
    data_dir = output_dir / "data"
    adapter_output_dir = output_dir / "adapter-output"
    adapter_output_dir.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset(
        data_dir,
        rows=args.rows,
        overlap_ratio=args.overlap_ratio,
        changed_ratio=args.changed_ratio,
        duplicate_ratio=args.duplicate_ratio,
        seed=args.seed,
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
        return measure(lambda: method(dataset, output_dir))
    except Exception as exc:  # pragma: no cover - defensive around optional adapters.
        return ScenarioResult(
            adapter=adapter.name,
            scenario=scenario,
            support_level="not_supported",
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            notes=["Adapter raised an exception; inspect dependency version and adapter notes."],
        )


if __name__ == "__main__":
    raise SystemExit(main())
