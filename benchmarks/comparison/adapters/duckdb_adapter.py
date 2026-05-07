"""DuckDB benchmark adapter."""

from __future__ import annotations

from pathlib import Path

from benchmarks.comparison.adapters.base import BenchmarkAdapter, unavailable_result
from benchmarks.comparison.adapters.utils import has_module
from benchmarks.comparison.measure import file_size
from benchmarks.comparison.models import DatasetPaths, ScenarioResult


class DuckDBAdapter(BenchmarkAdapter):
    """Adapter for DuckDB SQL implementations."""

    name = "duckdb"
    missing_reason = "Install duckdb via uniqdiff[benchmark]."

    def is_available(self) -> bool:
        return has_module("duckdb")

    def warmup(self) -> None:
        if self.is_available():
            import duckdb  # noqa: F401

    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_presence_by_key",
                reason=self.missing_reason,
                support_level="native",
            )
        import duckdb

        with duckdb.connect(":memory:") as conn:
            only_left = conn.execute(
                "SELECT COUNT(*) FROM read_csv_auto(?) l ANTI JOIN read_csv_auto(?) r USING (id)",
                [dataset.left_csv, dataset.right_csv],
            ).fetchone()[0]
            only_right = conn.execute(
                "SELECT COUNT(*) FROM read_csv_auto(?) r ANTI JOIN read_csv_auto(?) l USING (id)",
                [dataset.right_csv, dataset.left_csv],
            ).fetchone()[0]
            common = conn.execute(
                "SELECT COUNT(*) FROM read_csv_auto(?) l SEMI JOIN read_csv_auto(?) r USING (id)",
                [dataset.left_csv, dataset.right_csv],
            ).fetchone()[0]
        return ScenarioResult(
            adapter=self.name,
            scenario="row_presence_by_key",
            support_level="native",
            status="ok",
            only_in_left_count=int(only_left),
            only_in_right_count=int(only_right),
            common_count=int(common),
            notes=["Implemented with SQL SEMI/ANTI joins over CSV scans."],
        )

    def duplicate_detection(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "duplicate_detection_by_key",
                reason=self.missing_reason,
                support_level="native",
            )
        import duckdb

        with duckdb.connect(":memory:") as conn:
            duplicate_count = conn.execute(
                """
                SELECT COALESCE(SUM(count_per_key - 1), 0)
                FROM (
                    SELECT id, COUNT(*) AS count_per_key
                    FROM read_csv_auto(?)
                    GROUP BY id
                    HAVING COUNT(*) > 1
                )
                """,
                [dataset.duplicate_csv],
            ).fetchone()[0]
        return ScenarioResult(
            adapter=self.name,
            scenario="duplicate_detection_by_key",
            support_level="native",
            status="ok",
            duplicate_count=int(duplicate_count),
        )

    def row_level_changed_fields(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "row_level_changed_fields_by_key",
                reason=self.missing_reason,
                support_level="custom_code",
            )
        import duckdb

        comparisons = " OR ".join(
            _distinct_sql(column) for column in dataset.metadata["compared_columns"]
        )
        field_sum = " + ".join(
            f"CASE WHEN {_distinct_sql(column)} THEN 1 ELSE 0 END"
            for column in dataset.metadata["compared_columns"]
        )
        with duckdb.connect(":memory:") as conn:
            row = conn.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE {comparisons}) AS changed_rows,
                  SUM({field_sum}) AS changed_fields
                FROM read_csv_auto(?) l
                JOIN read_csv_auto(?) r USING (id)
                """,
                [dataset.left_csv, dataset.right_csv],
            ).fetchone()
        return ScenarioResult(
            adapter=self.name,
            scenario="row_level_changed_fields_by_key",
            support_level="custom_code",
            status="ok",
            changed_rows_count=int(row[0] or 0),
            changed_fields_count=int(row[1] or 0),
            notes=["Implemented with explicit SQL comparisons per field."],
        )

    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        if not self.is_available():
            return unavailable_result(
                self.name,
                "large_output_handling",
                reason=self.missing_reason,
                support_level="native",
            )
        import duckdb

        output = output_dir / "duckdb-large-output.csv"
        output_sql = str(output).replace("\\", "/").replace("'", "''")
        with duckdb.connect(":memory:") as conn:
            conn.execute(
                f"""
                COPY (
                    SELECT 'only_in_left' AS section, l.*
                    FROM read_csv_auto(?) l
                    ANTI JOIN read_csv_auto(?) r USING (id)
                ) TO '{output_sql}' (HEADER, DELIMITER ',')
                """,
                [dataset.left_csv, dataset.right_csv],
            )
        return ScenarioResult(
            adapter=self.name,
            scenario="large_output_handling",
            support_level="native",
            status="ok",
            output_bytes=file_size(output),
            notes=["Uses DuckDB COPY to write query output."],
        )

    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        return ScenarioResult(
            adapter=self.name,
            scenario="implementation_setup_complexity",
            support_level="custom_code",
            status="ok",
            extra={"install": "pip install duckdb", "typical_lines_of_code": "medium"},
        )


def _distinct_sql(column: str) -> str:
    quoted = '"' + column.replace('"', '""') + '"'
    return f"COALESCE(CAST(l.{quoted} AS VARCHAR), '') != COALESCE(CAST(r.{quoted} AS VARCHAR), '')"
