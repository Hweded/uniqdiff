"""uniqdiff benchmark adapter."""

from __future__ import annotations

from pathlib import Path

from benchmarks.comparison.adapters.base import BenchmarkAdapter, result
from benchmarks.comparison.adapters.utils import changed_rows, read_csv_rows
from benchmarks.comparison.measure import file_size
from benchmarks.comparison.models import DatasetPaths, ScenarioResult
from uniqdiff import compare_files, duplicates_source


class UniqdiffAdapter(BenchmarkAdapter):
    """Adapter for the package under test."""

    name = "uniqdiff"

    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        compared = compare_files(
            dataset.left_csv,
            dataset.right_csv,
            format="csv",
            key="id",
            include_common=True,
        )
        item = result(adapter=self.name, scenario="row_presence_by_key", support_level="native")
        item.only_in_left_count = compared.stats.only_in_first_count
        item.only_in_right_count = compared.stats.only_in_second_count
        item.common_count = compared.stats.common_count
        return item

    def duplicate_detection(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        duplicates = duplicates_source(dataset.duplicate_csv, kind="csv", key="id")
        item = result(
            adapter=self.name,
            scenario="duplicate_detection_by_key",
            support_level="native",
        )
        item.duplicate_count = len(duplicates)
        return item

    def row_level_changed_fields(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        left = read_csv_rows(dataset.left_csv)
        right = read_csv_rows(dataset.right_csv)
        changed_row_count, changed_field_count = changed_rows(left, right)
        item = result(
            adapter=self.name,
            scenario="row_level_changed_fields_by_key",
            support_level="custom_code",
            notes=["uniqdiff core reports presence; field-level row diff belongs in uniqrowdiff."],
        )
        item.changed_rows_count = changed_row_count
        item.changed_fields_count = changed_field_count
        return item

    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        output = output_dir / "uniqdiff-large-output.jsonl"
        compared = compare_files(
            dataset.left_csv,
            dataset.right_csv,
            format="csv",
            key="id",
            mode="disk",
            result_mode="file",
            output=str(output),
            temp_dir=str(output_dir),
        )
        item = result(adapter=self.name, scenario="large_output_handling", support_level="native")
        item.only_in_left_count = compared.stats.only_in_first_count
        item.only_in_right_count = compared.stats.only_in_second_count
        item.common_count = compared.stats.common_count
        item.output_bytes = file_size(output)
        return item

    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        item = result(
            adapter=self.name,
            scenario="implementation_setup_complexity",
            support_level="native",
        )
        item.extra = {
            "install": "pip install uniqdiff",
            "typical_lines_of_code": "low",
            "primary_fit": "exact comparison engine and CLI",
        }
        return item
