"""Adapter interface for benchmarked tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from benchmarks.comparison.models import DatasetPaths, ScenarioResult, SupportLevel


class BenchmarkAdapter(ABC):
    """Base class for cross-tool benchmark adapters."""

    name: str

    def is_available(self) -> bool:
        """Return whether optional runtime dependencies are installed."""

        return True

    def missing_result(self, scenario: str, *, reason: str) -> ScenarioResult:
        """Return a not-supported result for missing optional dependencies."""

        return ScenarioResult(
            adapter=self.name,
            scenario=scenario,
            support_level="not_supported",
            status="skipped",
            notes=[reason],
        )

    @abstractmethod
    def row_presence(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        """CSV row presence by key."""

    @abstractmethod
    def duplicate_detection(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        """Duplicate detection by key."""

    @abstractmethod
    def row_level_changed_fields(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        """Row-level changed fields by key."""

    @abstractmethod
    def large_output_handling(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        """Large output handling scenario."""

    @abstractmethod
    def setup_complexity(self, dataset: DatasetPaths, output_dir: Path) -> ScenarioResult:
        """Implementation/setup complexity scenario."""


def unavailable_result(
    adapter: str,
    scenario: str,
    *,
    reason: str,
    support_level: SupportLevel = "not_supported",
) -> ScenarioResult:
    """Create a skipped result for an unavailable adapter."""

    return ScenarioResult(
        adapter=adapter,
        scenario=scenario,
        support_level=support_level,
        status="skipped",
        notes=[reason],
    )


def result(
    *,
    adapter: str,
    scenario: str,
    support_level: SupportLevel,
    status: str = "ok",
    notes: list[str] | None = None,
) -> ScenarioResult:
    """Create a basic scenario result."""

    return ScenarioResult(
        adapter=adapter,
        scenario=scenario,
        support_level=support_level,
        status=status,
        notes=[] if notes is None else notes,
    )
