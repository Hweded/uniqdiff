"""Internal backend protocol types."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional, Protocol, Union

from uniqdiff.result import CompareResult
from uniqdiff.tokens import TokenFactory


class CompareBackend(Protocol):
    """Protocol implemented by exact comparison backends."""

    def __call__(
        self,
        first: Iterable[Any],
        second: Iterable[Any],
        *,
        token_factory: TokenFactory,
        include_common: bool,
        include_duplicates: bool,
        chunk_size: int,
        temp_dir: Optional[str],
        disk_limit: Optional[Union[str, int]],
        mode: str,
        strategy: str,
        metadata: dict[str, Any],
        output: Optional[str] = None,
        result_mode: str = "memory",
        **kwargs: Any,
    ) -> CompareResult:
        """Compare two inputs and return a normalized result."""


class DuplicatesBackend(Protocol):
    """Protocol implemented by duplicate-detection backends."""

    def __call__(
        self,
        data: Iterable[Any],
        *,
        token_factory: TokenFactory,
        chunk_size: int,
        temp_dir: Optional[str],
        disk_limit: Optional[Union[str, int]],
        **kwargs: Any,
    ) -> list[Any]:
        """Return duplicate values from one input."""
