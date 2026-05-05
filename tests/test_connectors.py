import importlib.util
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from uniqdiff import (
    CSVConnector,
    InvalidInputError,
    MissingOptionalDependencyError,
    ParquetConnector,
    compare_sources,
    connect,
    create_connector,
    duplicates_source,
    list_connectors,
    register_connector,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_builtin_connectors_are_registered():
    names = list_connectors()

    assert "csv" in names
    assert "file" in names
    assert "iterable" in names
    assert "jsonl" in names
    assert "parquet" in names
    assert "tsv" in names
    assert "txt" in names


def test_connect_infers_file_connector_for_paths():
    connector = connect(FIXTURES / "left.csv", format="csv")

    assert connector.describe()["connector"] == "file"
    assert list(connector.open()) == [
        {"id": "1", "name": "Ann"},
        {"id": "2", "name": "Bob"},
    ]


def test_compare_sources_with_csv_connectors():
    result = compare_sources(
        FIXTURES / "left.csv",
        FIXTURES / "right.csv",
        first_kind="csv",
        second_kind="csv",
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]
    assert result.metadata["connectors"]["first"]["connector"] == "csv"


def test_compare_sources_with_tsv_connectors():
    result = compare_sources(
        FIXTURES / "left.tsv",
        FIXTURES / "right.tsv",
        first_kind="tsv",
        second_kind="tsv",
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]
    assert result.metadata["connectors"]["first"]["connector"] == "tsv"


def test_compare_sources_with_file_connector_options():
    result = compare_sources(
        FIXTURES / "left_semicolon.csv",
        FIXTURES / "right_semicolon.csv",
        first_options={"format": "csv", "delimiter": ";"},
        second_options={"format": "csv", "delimiter": ";"},
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]
    assert result.metadata["connectors"]["first"]["delimiter"] == ";"


def test_compare_sources_with_iterables():
    result = compare_sources([1, 2, 3], [2, 4])

    assert result.only_in_first == [1, 3]
    assert result.only_in_second == [4]
    assert result.metadata["connectors"]["first"]["connector"] == "iterable"


def test_duplicates_source_with_text_connector():
    result = duplicates_source(FIXTURES / "dupes.txt", kind="txt")

    assert result == ["a", "b"]


def test_create_connector_rejects_unknown_kind():
    with pytest.raises(InvalidInputError):
        create_connector("missing", [])


def test_custom_connector_registration():
    class StaticConnector:
        name = "static"

        def __init__(self, source: list[Any]) -> None:
            self.source = source

        def open(self) -> Iterator[Any]:
            yield from self.source

        def describe(self) -> dict[str, Any]:
            return {"connector": self.name}

    register_connector("static", StaticConnector)
    result = compare_sources([1, 2], [2, 3], first_kind="static", second_kind="static")

    assert result.only_in_first == [1]
    assert result.only_in_second == [3]
    assert result.metadata["connectors"]["first"] == {"connector": "static"}


def test_existing_connector_is_passed_through():
    connector = CSVConnector(FIXTURES / "left.csv")

    assert connect(connector) is connector


def test_parquet_connector_reports_missing_optional_dependency_when_pyarrow_is_absent():
    if importlib.util.find_spec("pyarrow") is not None:
        pytest.skip("pyarrow is installed")

    connector = ParquetConnector(FIXTURES / "missing.parquet")

    with pytest.raises(MissingOptionalDependencyError, match="uniqdiff\\[parquet\\]"):
        list(connector.open())
