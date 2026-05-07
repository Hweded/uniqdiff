"""pandas benchmark adapter."""

from __future__ import annotations

from pathlib import Path

from benchmarks.comparison.adapters.base import BenchmarkAdapter, unavailable_result
from benchmarks.comparison.adapters.utils import has_module
from benchmarks.comparison.measure import file_size
from benchmarks.comparison.models import DatasetPaths, ScenarioResult


class PandasAdapter(BenchmarkAdapter):
    """Adapter for pandas implementations."""

    name = "pandas"
    missing_reason = "Install pandas via uniqdiff[benchmark]."

    def is_available(self) -> bool:
        return has_module("pandas")

    def warmup(self) -> None:
        if self.is_available():
            import pandas  # noqa: F401

    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_presence_by_key",
                reason=self.missing_reason,
                support_level="custom_code",
            )
        import pandas as pd

        left = pd.read_csv(dataset.left_csv, dtype=str, keep_default_na=False)
        right = pd.read_csv(dataset.right_csv, dtype=str, keep_default_na=False)
        merged = left[["id"]].merge(right[["id"]], on="id", how="outer", indicator=True)
        return ScenarioResult(
            adapter=self.name,
            scenario="row_presence_by_key",
            support_level="custom_code",
            status="ok",
            only_in_left_count=int((merged["_merge"] == "left_only").sum()),
            only_in_right_count=int((merged["_merge"] == "right_only").sum()),
            common_count=int((merged["_merge"] == "both").sum()),
            notes=["Implemented with merge(indicator=True)."],
        )

    def duplicate_detection(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "duplicate_detection_by_key",
                reason=self.missing_reason,
                support_level="native",
            )
        import pandas as pd

        rows = pd.read_csv(dataset.duplicate_csv, dtype=str, keep_default_na=False)
        duplicates = rows.duplicated(subset=["id"], keep="first")
        return ScenarioResult(
            adapter=self.name,
            scenario="duplicate_detection_by_key",
            support_level="native",
            status="ok",
            duplicate_count=int(duplicates.sum()),
        )

    def row_level_changed_fields(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_level_changed_fields_by_key",
                reason=self.missing_reason,
                support_level="custom_code",
            )
        import pandas as pd

        left = pd.read_csv(dataset.left_csv, dtype=str, keep_default_na=False).set_index("id")
        right = pd.read_csv(dataset.right_csv, dtype=str, keep_default_na=False).set_index("id")
        common = left.index.intersection(right.index)
        columns = [column for column in dataset.metadata["compared_columns"] if column in right]
        changed = left.loc[common, columns].ne(right.loc[common, columns])
        return ScenarioResult(
            adapter=self.name,
            scenario="row_level_changed_fields_by_key",
            support_level="custom_code",
            status="ok",
            changed_rows_count=int(changed.any(axis=1).sum()),
            changed_fields_count=int(changed.sum().sum()),
            notes=["Implemented with index alignment and DataFrame.ne()."],
        )

    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "large_output_handling",
                reason=self.missing_reason,
                support_level="partial",
            )
        import pandas as pd

        left = pd.read_csv(dataset.left_csv, dtype=str, keep_default_na=False)
        right = pd.read_csv(dataset.right_csv, dtype=str, keep_default_na=False)
        merged = left.merge(right[["id"]], on="id", how="left", indicator=True)
        output = output_dir / "pandas-large-output.jsonl"
        merged.loc[merged["_merge"] == "left_only"].to_json(output, orient="records", lines=True)
        return ScenarioResult(
            adapter=self.name,
            scenario="large_output_handling",
            support_level="partial",
            status="ok",
            output_bytes=file_size(output),
            notes=["Works, but full DataFrames are typically materialized."],
        )

    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="implementation_setup_complexity",
            support_level="custom_code",
            status="ok",
            extra={"install": "pip install pandas", "typical_lines_of_code": "medium"},
        )
