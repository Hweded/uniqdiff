"""Result types for comparisons."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class CompareStats:
    """Statistics collected during comparison."""

    first_count: int = 0
    second_count: int = 0
    unique_first_count: int = 0
    unique_second_count: int = 0
    only_in_first_count: int = 0
    only_in_second_count: int = 0
    common_count: int = 0
    duplicate_first_count: int = 0
    duplicate_second_count: int = 0
    mode: str = "memory"
    strategy: str = "hash"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""

        return asdict(self)


@dataclass
class CompareResult:
    """Full comparison result.

    Large-data workflows should prefer streaming or file output instead of keeping
    all result lists in memory.
    """

    only_in_first: list[Any] = field(default_factory=list)
    only_in_second: list[Any] = field(default_factory=list)
    common: Optional[list[Any]] = None
    unique: list[Any] = field(default_factory=list)
    duplicates_first: Optional[list[Any]] = None
    duplicates_second: Optional[list[Any]] = None
    stats: CompareStats = field(default_factory=CompareStats)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""

        return {
            "only_in_first": self.only_in_first,
            "only_in_second": self.only_in_second,
            "common": self.common,
            "unique": self.unique,
            "duplicates_first": self.duplicates_first,
            "duplicates_second": self.duplicates_second,
            "stats": self.stats.to_dict(),
            "metadata": self.metadata,
            "warnings": self.warnings,
        }

    def iter_unique(self) -> Iterable[Any]:
        """Yield unique differences lazily from the stored result."""

        output = self.metadata.get("output")
        if output and self.metadata.get("result_mode") == "file":
            from uniqdiff.output import iter_result_values

            yield from iter_result_values(output, sections=("only_in_first", "only_in_second"))
            return

        yield from self.only_in_first
        yield from self.only_in_second

    def iter_section(self, section: str) -> Iterable[Any]:
        """Yield values for one result section from memory or file-backed output."""

        output = self.metadata.get("output")
        if output and self.metadata.get("result_mode") == "file":
            from uniqdiff.output import iter_result_values

            yield from iter_result_values(output, sections=(section,))
            return

        values = _memory_section_values(self, section)
        if values is not None:
            yield from values


def _memory_section_values(result: CompareResult, section: str) -> Optional[list[Any]]:
    sections = {
        "only_in_first": result.only_in_first,
        "only_in_second": result.only_in_second,
        "common": result.common,
        "unique": result.unique,
        "duplicates_first": result.duplicates_first,
        "duplicates_second": result.duplicates_second,
    }
    return sections.get(section)
