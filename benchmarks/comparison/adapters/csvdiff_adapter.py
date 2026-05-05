"""csv-diff/csvdiff benchmark adapter."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from benchmarks.comparison.adapters.base import BenchmarkAdapter, unavailable_result
from benchmarks.comparison.adapters.utils import has_module, read_csv_rows, row_presence_counts
from benchmarks.comparison.models import DatasetPaths, ScenarioResult


class CsvDiffAdapter(BenchmarkAdapter):
    """Adapter for csv-diff style tools."""

    name = "csv-diff"
    missing_reason = "Install csv-diff via uniqdiff[benchmark]."

    def is_available(self) -> bool:
        return has_module("csv_diff")

    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_presence_by_key",
                reason=self.missing_reason,
                support_level="partial",
            )
        diff = _csv_diff(dataset)
        counts = row_presence_counts(
            read_csv_rows(dataset.left_csv),
            read_csv_rows(dataset.right_csv),
        )
        return ScenarioResult(
            adapter=self.name,
            scenario="row_presence_by_key",
            support_level="partial",
            status="ok",
            only_in_left_count=len(diff.get("removed", [])),
            only_in_right_count=len(diff.get("added", [])),
            common_count=counts["common"],
            notes=[
                "csv-diff reports added/removed/changed natively; "
                "common count is computed by adapter glue.",
            ],
        )

    def duplicate_detection(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="duplicate_detection_by_key",
            support_level="not_primary_use_case",
            status="skipped",
            notes=[
                "csv-diff focuses on comparing two CSV files, "
                "not single-file duplicate detection.",
            ],
        )

    def row_level_changed_fields(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_level_changed_fields_by_key",
                reason=self.missing_reason,
                support_level="native",
            )
        diff = _csv_diff(dataset)
        changed = diff.get("changed", [])
        changed_fields = 0
        for row in changed:
            changes = row.get("changes", {})
            changed_fields += len(changes)
        return ScenarioResult(
            adapter=self.name,
            scenario="row_level_changed_fields_by_key",
            support_level="native",
            status="ok",
            changed_rows_count=len(changed),
            changed_fields_count=changed_fields,
        )

    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="large_output_handling",
            support_level="partial",
            status="skipped",
            notes=[
                "Adapter skeleton does not stream csv-diff output; "
                "compare separately for CLI output behavior.",
            ],
        )

    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="implementation_setup_complexity",
            support_level="native",
            status="ok",
            extra={"install": "pip install csv-diff", "typical_lines_of_code": "low"},
        )


def _csv_diff(dataset: DatasetPaths) -> dict[str, object]:
    from csv_diff import compare, load_csv

    with ExitStack() as stack:
        left_file = stack.enter_context(
            Path(dataset.left_csv).open("r", encoding="utf-8", newline="")
        )
        right_file = stack.enter_context(
            Path(dataset.right_csv).open("r", encoding="utf-8", newline="")
        )
        return compare(load_csv(left_file, key="id"), load_csv(right_file, key="id"))
