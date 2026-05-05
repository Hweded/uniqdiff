"""JSONL and Markdown reporting for cross-tool benchmarks."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from benchmarks.comparison.models import ScenarioResult

DISCLAIMER = (
    "Benchmark results are workload-dependent. They should be used to understand "
    "fit-by-use-case, setup complexity, memory behavior, and output handling rather "
    "than to claim that one tool is universally faster."
)


def write_jsonl(results: list[ScenarioResult], output: Path) -> None:
    """Write one result object per JSONL line."""

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            file.write("\n")


def write_markdown(results: list[ScenarioResult], output: Path) -> None:
    """Write a human-readable benchmark report."""

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Benchmark Report",
        "",
        f"> {DISCLAIMER}",
        "",
        "## Fit By Use Case",
        "",
        "Skipped rows keep the adapter's intended support level when optional deps are missing.",
        "",
        _fit_table(results),
        "",
        "## Measurements",
        "",
        _measurement_table(results),
        "",
        "## Support Levels",
        "",
        "- `native`: directly supported by the tool's primary API.",
        "- `custom_code`: possible, but requires user-written glue logic.",
        "- `partial`: supported only for part of the scenario.",
        "- `not_supported`: no adapter implementation or practical support.",
        "- `not_primary_use_case`: possible but not what the tool is mainly for.",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


def _fit_table(results: list[ScenarioResult]) -> str:
    by_scenario: dict[str, list[ScenarioResult]] = defaultdict(list)
    for result in results:
        by_scenario[result.scenario].append(result)

    lines = ["| Scenario | Native | Custom code | Partial | Not primary | Not supported |"]
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for scenario in sorted(by_scenario):
        buckets = defaultdict(list)
        for result in by_scenario[scenario]:
            buckets[result.support_level].append(result.adapter)
        template = (
            "| {scenario} | {native} | {custom} | {partial} | "
            "{not_primary} | {not_supported} |"
        )
        lines.append(
            template.format(
                scenario=scenario,
                native=", ".join(sorted(buckets["native"])) or "-",
                custom=", ".join(sorted(buckets["custom_code"])) or "-",
                partial=", ".join(sorted(buckets["partial"])) or "-",
                not_primary=", ".join(sorted(buckets["not_primary_use_case"])) or "-",
                not_supported=", ".join(sorted(buckets["not_supported"])) or "-",
            )
        )
    return "\n".join(lines)


def _measurement_table(results: list[ScenarioResult]) -> str:
    lines = [
        "| Adapter | Scenario | Support | Status | Seconds | Peak MB | Output bytes | Key counts |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        peak_mb = (
            round(result.peak_memory_bytes / 1024 / 1024, 3)
            if result.peak_memory_bytes is not None
            else "-"
        )
        key_counts = (
            f"left={result.only_in_left_count}, right={result.only_in_right_count}, "
            f"common={result.common_count}, dupes={result.duplicate_count}, "
            f"changed_rows={result.changed_rows_count}"
        )
        template = (
            "| {adapter} | {scenario} | {support} | {status} | {seconds} | "
            "{peak} | {output} | {counts} |"
        )
        lines.append(
            template.format(
                adapter=result.adapter,
                scenario=result.scenario,
                support=result.support_level,
                status=result.status,
                seconds=result.elapsed_seconds if result.elapsed_seconds is not None else "-",
                peak=peak_mb,
                output=result.output_bytes,
                counts=key_counts,
            )
        )
    return "\n".join(lines)
