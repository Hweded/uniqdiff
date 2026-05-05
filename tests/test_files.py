import gzip
import importlib
import importlib.util
from pathlib import Path

import pytest

from uniqdiff import MissingOptionalDependencyError, compare_files

FIXTURES = Path(__file__).parent / "fixtures"


def test_compare_csv_files():
    result = compare_files(
        str(FIXTURES / "left.csv"),
        str(FIXTURES / "right.csv"),
        format="csv",
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_compare_jsonl_files():
    result = compare_files(
        str(FIXTURES / "left.jsonl"),
        str(FIXTURES / "right.jsonl"),
        format="jsonl",
        key="id",
    )

    assert result.only_in_first == [{"id": 1}]
    assert result.only_in_second == [{"id": 3}]


def test_compare_text_files():
    result = compare_files(str(FIXTURES / "left.txt"), str(FIXTURES / "right.txt"), format="txt")

    assert result.only_in_first == ["a"]
    assert result.only_in_second == ["c"]


def test_compare_tsv_files_with_auto_format():
    result = compare_files(
        str(FIXTURES / "left.tsv"),
        str(FIXTURES / "right.tsv"),
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_compare_gzip_csv_files_with_auto_format():
    left = FIXTURES / "left.csv.gz"
    right = FIXTURES / "right.csv.gz"
    left.unlink(missing_ok=True)
    right.unlink(missing_ok=True)
    try:
        _write_gzip_text(left, (FIXTURES / "left.csv").read_text(encoding="utf-8"))
        _write_gzip_text(right, (FIXTURES / "right.csv").read_text(encoding="utf-8"))

        result = compare_files(str(left), str(right), key="id")
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_compare_gzip_jsonl_files_with_auto_format():
    left = FIXTURES / "left.jsonl.gz"
    right = FIXTURES / "right.jsonl.gz"
    left.unlink(missing_ok=True)
    right.unlink(missing_ok=True)
    try:
        _write_gzip_text(left, (FIXTURES / "left.jsonl").read_text(encoding="utf-8"))
        _write_gzip_text(right, (FIXTURES / "right.jsonl").read_text(encoding="utf-8"))

        result = compare_files(str(left), str(right), key="id")
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.only_in_first == [{"id": 1}]
    assert result.only_in_second == [{"id": 3}]


def test_compare_csv_files_with_custom_delimiter():
    result = compare_files(
        str(FIXTURES / "left_semicolon.csv"),
        str(FIXTURES / "right_semicolon.csv"),
        format="csv",
        delimiter=";",
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_compare_csv_files_without_header_and_with_fieldnames():
    result = compare_files(
        str(FIXTURES / "left_no_header.csv"),
        str(FIXTURES / "right_no_header.csv"),
        format="csv",
        has_header=False,
        fieldnames=("id", "name"),
        key="id",
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_compare_csv_files_without_header_and_fieldnames_yields_lists():
    result = compare_files(
        str(FIXTURES / "left_no_header.csv"),
        str(FIXTURES / "right_no_header.csv"),
        format="csv",
        has_header=False,
    )

    assert result.only_in_first == [["1", "Ann"]]
    assert result.only_in_second == [["3", "Cara"]]


def test_compare_parquet_files_when_pyarrow_is_available():
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow is not installed")

    left = FIXTURES / "left.parquet"
    right = FIXTURES / "right.parquet"
    left.unlink(missing_ok=True)
    right.unlink(missing_ok=True)
    try:
        _write_parquet_rows(left, [{"id": 1, "name": "Ann"}, {"id": 2, "name": "Bob"}])
        _write_parquet_rows(right, [{"id": 2, "name": "Bob"}, {"id": 3, "name": "Cara"}])

        result = compare_files(str(left), str(right), key="id", columns=("id", "name"))
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.only_in_first == [{"id": 1, "name": "Ann"}]
    assert result.only_in_second == [{"id": 3, "name": "Cara"}]


def test_compare_parquet_files_reports_missing_optional_dependency_when_pyarrow_is_absent():
    if importlib.util.find_spec("pyarrow") is not None:
        pytest.skip("pyarrow is installed")

    with pytest.raises(MissingOptionalDependencyError, match="uniqdiff\\[parquet\\]"):
        compare_files(str(FIXTURES / "missing.parquet"), str(FIXTURES / "missing.parquet"))


def _write_gzip_text(path: Path, content: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(content)


def _write_parquet_rows(path: Path, rows: list[dict[str, object]]) -> None:
    pyarrow = importlib.import_module("pyarrow")
    parquet = importlib.import_module("pyarrow.parquet")
    table = pyarrow.Table.from_pylist(rows)
    parquet.write_table(table, path)
