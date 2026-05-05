"""Connector registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from uniqdiff.connectors.base import IterableConnector, SourceConnector
from uniqdiff.connectors.files import (
    CSVConnector,
    FileConnector,
    JSONLConnector,
    ParquetConnector,
    TextConnector,
    TSVConnector,
)
from uniqdiff.exceptions import InvalidInputError

ConnectorFactory = Callable[..., SourceConnector]


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


class ConnectorRegistry:
    """Registry for source connector factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ConnectorFactory] = {}

    def register(self, name: str, factory: ConnectorFactory) -> None:
        normalized = _normalize_name(name)
        if not normalized:
            raise InvalidInputError("Connector name must not be empty")
        self._factories[normalized] = factory

    def create(self, name: str, source: Any, **options: Any) -> SourceConnector:
        normalized = _normalize_name(name)
        try:
            factory = self._factories[normalized]
        except KeyError as exc:
            raise InvalidInputError(f"Unknown connector: {name!r}") from exc
        return factory(source, **options)

    def names(self) -> list[str]:
        return sorted(self._factories)


def default_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register("iterable", IterableConnector)
    registry.register("file", FileConnector)
    registry.register("csv", CSVConnector)
    registry.register("jsonl", JSONLConnector)
    registry.register("parquet", ParquetConnector)
    registry.register("pq", ParquetConnector)
    registry.register("tsv", TSVConnector)
    registry.register("tab", TSVConnector)
    registry.register("txt", TextConnector)
    registry.register("text", TextConnector)
    return registry


DEFAULT_REGISTRY = default_registry()


def register_connector(name: str, factory: ConnectorFactory) -> None:
    """Register a connector factory in the default registry."""

    DEFAULT_REGISTRY.register(name, factory)


def list_connectors() -> list[str]:
    """Return connector names registered in the default registry."""

    return DEFAULT_REGISTRY.names()


def create_connector(name: str, source: Any, **options: Any) -> SourceConnector:
    """Create a connector from the default registry."""

    return DEFAULT_REGISTRY.create(name, source, **options)


def connect(
    source: Any,
    *,
    kind: Optional[str] = None,
    **options: Any,
) -> SourceConnector:
    """Create or pass through a source connector.

    If `kind` is omitted, strings and paths use the `file` connector and other values
    use the `iterable` connector.
    """

    if isinstance(source, SourceConnector):
        return source

    selected_kind = kind
    if selected_kind is None:
        selected_kind = "file" if isinstance(source, (str, Path)) else "iterable"

    return create_connector(selected_kind, source, **options)
