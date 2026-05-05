"""Source connector API."""

from uniqdiff.connectors.base import IterableConnector, SourceConnector
from uniqdiff.connectors.files import (
    CSVConnector,
    FileConnector,
    JSONLConnector,
    ParquetConnector,
    TextConnector,
    TSVConnector,
)
from uniqdiff.connectors.registry import (
    ConnectorFactory,
    ConnectorRegistry,
    connect,
    create_connector,
    list_connectors,
    register_connector,
)

__all__ = [
    "CSVConnector",
    "ConnectorFactory",
    "ConnectorRegistry",
    "FileConnector",
    "IterableConnector",
    "JSONLConnector",
    "ParquetConnector",
    "SourceConnector",
    "TSVConnector",
    "TextConnector",
    "connect",
    "create_connector",
    "list_connectors",
    "register_connector",
]
