"""Shared benchmark models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

SupportLevel = Literal[
    "native",
    "custom_code",
    "partial",
    "not_supported",
    "not_primary_use_case",
]


@dataclass(frozen=True)
class Scenario:
    """One benchmark scenario definition."""

    name: str
    description: str


@dataclass
class ScenarioResult:
    """Normalized adapter output for a scenario."""

    adapter: str
    scenario: str
    support_level: SupportLevel
    status: str
    elapsed_seconds: Optional[float] = None
    peak_memory_bytes: Optional[int] = None
    output_bytes: int = 0
    only_in_left_count: Optional[int] = None
    only_in_right_count: Optional[int] = None
    common_count: Optional[int] = None
    duplicate_count: Optional[int] = None
    changed_rows_count: Optional[int] = None
    changed_fields_count: Optional[int] = None
    notes: list[str] = field(default_factory=list)
    error: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSONL-friendly representation."""

        return asdict(self)


@dataclass(frozen=True)
class DatasetPaths:
    """Generated dataset paths."""

    left_csv: str
    right_csv: str
    duplicate_csv: str
