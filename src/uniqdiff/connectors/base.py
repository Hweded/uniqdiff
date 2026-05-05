"""Connector protocols and helpers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SourceConnector(Protocol):
    """Protocol implemented by all source connectors."""

    name: str

    def open(self) -> Iterator[Any]:
        """Return an iterator over source items."""

    def describe(self) -> dict[str, Any]:
        """Return metadata describing the source."""


class IterableConnector:
    """Connector for already parsed Python iterables."""

    name = "iterable"

    def __init__(self, source: Iterable[Any]) -> None:
        self.source = source

    def open(self) -> Iterator[Any]:
        yield from self.source

    def describe(self) -> dict[str, Any]:
        return {"connector": self.name, "source_type": type(self.source).__name__}
