"""DataComPy benchmark adapter."""

from __future__ import annotations

from pathlib import Path

from benchmarks.comparison.adapters.base import BenchmarkAdapter, unavailable_result
from benchmarks.comparison.adapters.utils import (
    changed_rows,
    has_module,
    read_csv_rows,
    row_presence_counts,
)
from benchmarks.comparison.models import DatasetPaths, ScenarioResult


class DataComPyAdapter(BenchmarkAdapter):
    """Adapter for DataComPy."""

    name = "datacompy"
    missing_reason = "Install datacompy and pandas via uniqdiff[benchmark]."

    def is_available(self) -> bool:
        return has_module("datacompy") and has_module("pandas")

    def warmup(self) -> None:
        if self.is_available():
            import datacompy  # noqa: F401
            import pandas  # noqa: F401

    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_presence_by_key",
                reason=self.missing_reason,
                support_level="partial",
            )
        comparison = self._compare(dataset)
        counts = row_presence_counts(
            read_csv_rows(dataset.left_csv),
            read_csv_rows(dataset.right_csv),
        )
        return ScenarioResult(
            adapter=self.name,
            scenario="row_presence_by_key",
            support_level="partial",
            status="ok",
            only_in_left_count=int(comparison.df1_unq_rows.shape[0]),
            only_in_right_count=int(comparison.df2_unq_rows.shape[0]),
            common_count=counts["common"],
            notes=[
                "DataComPy focuses on dataframe comparison reports; "
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
                "DataComPy is primarily for comparing two datasets, "
                "not single-source duplicate detection.",
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
        comparison = self._compare(dataset)
        changed_row_count, changed_field_count = changed_rows(
            read_csv_rows(dataset.left_csv),
            read_csv_rows(dataset.right_csv),
            columns=dataset.metadata["compared_columns"],
        )
        return ScenarioResult(
            adapter=self.name,
            scenario="row_level_changed_fields_by_key",
            support_level="native",
            status="ok",
            changed_rows_count=changed_row_count,
            changed_fields_count=changed_field_count,
            notes=[
                "DataComPy provides rich row/column comparison reports; "
                "normalized counts are computed for comparability.",
            ],
            extra={"report_available": bool(getattr(comparison, "report", None))},
        )

    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "large_output_handling",
                reason=self.missing_reason,
                support_level="not_primary_use_case",
            )
        comparison = self._compare(dataset)
        output = output_dir / "datacompy-report.txt"
        output.write_text(comparison.report(), encoding="utf-8")
        return ScenarioResult(
            adapter=self.name,
            scenario="large_output_handling",
            support_level="not_primary_use_case",
            status="ok",
            output_bytes=output.stat().st_size,
            notes=[
                "DataComPy reports are useful, but this is not a streaming "
                "large-diff output path.",
            ],
        )

    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="implementation_setup_complexity",
            support_level="native",
            status="ok",
            extra={"install": "pip install datacompy pandas", "typical_lines_of_code": "medium"},
        )

    def _compare(self, dataset: DatasetPaths):
        import pandas as pd
        from datacompy.core import Compare

        left = pd.read_csv(dataset.left_csv, dtype=str, keep_default_na=False)
        right = pd.read_csv(dataset.right_csv, dtype=str, keep_default_na=False)
        try:
            return Compare(
                left,
                right,
                join_columns=["id"],
                df1_name="left",
                df2_name="right",
            )
        except TypeError:
            return Compare(
                left,
                right,
                join_columns="id",
                df1_name="left",
                df2_name="right",
            )
