"""Benchmark adapter registry."""

from benchmarks.comparison.adapters.base import BenchmarkAdapter
from benchmarks.comparison.adapters.csvdiff_adapter import CsvDiffAdapter
from benchmarks.comparison.adapters.datacompy_adapter import DataComPyAdapter
from benchmarks.comparison.adapters.duckdb_adapter import DuckDBAdapter
from benchmarks.comparison.adapters.pandas_adapter import PandasAdapter
from benchmarks.comparison.adapters.uniqdiff_adapter import UniqdiffAdapter


def default_adapters() -> list[BenchmarkAdapter]:
    """Return adapters used by the benchmark suite."""

    return [
        UniqdiffAdapter(),
        PandasAdapter(),
        DuckDBAdapter(),
        CsvDiffAdapter(),
        DataComPyAdapter(),
    ]


__all__ = [
    "BenchmarkAdapter",
    "CsvDiffAdapter",
    "DataComPyAdapter",
    "DuckDBAdapter",
    "PandasAdapter",
    "UniqdiffAdapter",
    "default_adapters",
]
