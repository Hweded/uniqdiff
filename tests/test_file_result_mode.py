import csv
import json
from pathlib import Path

import pytest

from uniqdiff import (
    InvalidInputError,
    compare,
    compare_files,
    iter_result_rows,
    iter_result_values,
)
from uniqdiff.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
TEMP_DIR = str(FIXTURES)


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_sqlite_file_result_mode_writes_jsonl():
    output = FIXTURES / "result-mode-sqlite.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2, 2, 3],
            [2, 3, 4, 4],
            mode="disk",
            include_common=True,
            include_duplicates=True,
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
            chunk_size=2,
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert result.only_in_first == []
    assert result.metadata["output"] == str(output)
    assert result.stats.only_in_first_count == 1
    assert result.stats.only_in_second_count == 1
    assert {"section": "only_in_first", "value": 1} in rows
    assert {"section": "only_in_second", "value": 4} in rows
    assert {"section": "common", "value": 2} in rows
    assert {"section": "duplicates_first", "value": 2} in rows
    assert {"section": "duplicates_second", "value": 4} in rows


@pytest.mark.parametrize("disk_strategy", ["hash_partition", "external_sort"])
def test_file_result_mode_for_other_disk_backends(disk_strategy):
    output = FIXTURES / f"result-mode-{disk_strategy}.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2, 3],
            [2, 4],
            mode="disk",
            disk_strategy=disk_strategy,
            partition_count=2,
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
            chunk_size=1,
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert result.unique == []
    assert result.metadata["result_mode"] == "file"
    assert result.stats.only_in_first_count == 2
    assert result.stats.only_in_second_count == 1
    assert any(row == {"section": "only_in_first", "value": 1} for row in rows)
    assert any(row == {"section": "only_in_second", "value": 4} for row in rows)


def test_hash_partition_file_result_mode_streams_sections():
    output = FIXTURES / "result-mode-hash-partition-stream.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2, 2, 3],
            [2, 3, 4, 4],
            mode="disk",
            disk_strategy="hash_partition",
            partition_count=2,
            include_common=True,
            include_duplicates=True,
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
            chunk_size=1,
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert result.only_in_first == []
    assert result.only_in_second == []
    assert result.common is None
    assert result.duplicates_first is None
    assert result.stats.only_in_first_count == 1
    assert result.stats.only_in_second_count == 1
    assert result.stats.common_count == 2
    assert result.stats.duplicate_first_count == 1
    assert result.stats.duplicate_second_count == 1
    assert {"section": "only_in_first", "value": 1} in rows
    assert {"section": "only_in_second", "value": 4} in rows
    assert {"section": "common", "value": 2} in rows
    assert {"section": "duplicates_first", "value": 2} in rows
    assert {"section": "duplicates_second", "value": 4} in rows


def test_external_sort_file_result_mode_streams_sections():
    output = FIXTURES / "result-mode-external-sort-stream.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2, 2, 3],
            [2, 3, 4, 4],
            mode="disk",
            disk_strategy="external_sort",
            include_common=True,
            include_duplicates=True,
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
            chunk_size=1,
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert result.only_in_first == []
    assert result.only_in_second == []
    assert result.common is None
    assert result.duplicates_first is None
    assert result.stats.only_in_first_count == 1
    assert result.stats.only_in_second_count == 1
    assert result.stats.common_count == 2
    assert result.stats.duplicate_first_count == 1
    assert result.stats.duplicate_second_count == 1
    assert {"section": "only_in_first", "value": 1} in rows
    assert {"section": "only_in_second", "value": 4} in rows
    assert {"section": "common", "value": 2} in rows
    assert {"section": "duplicates_first", "value": 2} in rows
    assert {"section": "duplicates_second", "value": 4} in rows


def test_file_result_mode_writes_csv():
    output = FIXTURES / "result-mode.csv"
    output.unlink(missing_ok=True)
    try:
        result = compare_files(
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            format="csv",
            key="id",
            mode="disk",
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
        )
        with output.open("r", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
    finally:
        output.unlink(missing_ok=True)

    assert result.stats.only_in_first_count == 1
    assert rows[0]["section"] == "only_in_first"
    assert json.loads(rows[0]["value"]) == {"id": "1", "name": "Ann"}


def test_lazy_result_rows_and_values_read_jsonl():
    output = FIXTURES / "lazy-result.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2, 3],
            [2, 4],
            mode="disk",
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
        )

        only_first = list(iter_result_values(output, sections=("only_in_first",)))
        unique = list(result.iter_unique())
        only_second = list(result.iter_section("only_in_second"))
    finally:
        output.unlink(missing_ok=True)

    assert only_first == [1, 3]
    assert unique == [1, 3, 4]
    assert only_second == [4]


def test_lazy_result_rows_read_csv():
    output = FIXTURES / "lazy-result.csv"
    output.unlink(missing_ok=True)
    try:
        compare_files(
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            format="csv",
            key="id",
            mode="disk",
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
        )
        rows = list(iter_result_rows(output))
    finally:
        output.unlink(missing_ok=True)

    assert rows == [
        {"section": "only_in_first", "value": {"id": "1", "name": "Ann"}},
        {"section": "only_in_second", "value": {"id": "3", "name": "Cara"}},
    ]


def test_jsonl_file_result_schema_is_backward_compatible():
    output = FIXTURES / "schema-result.jsonl"
    output.unlink(missing_ok=True)
    try:
        compare(
            [1, 2],
            [2, 3],
            mode="disk",
            include_common=True,
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert rows
    assert all(set(row) == {"section", "value"} for row in rows)
    assert {row["section"] for row in rows} == {
        "only_in_first",
        "only_in_second",
        "common",
    }


def test_csv_file_result_schema_is_backward_compatible():
    output = FIXTURES / "schema-result.csv"
    output.unlink(missing_ok=True)
    try:
        compare(
            [1],
            [2],
            mode="disk",
            result_mode="file",
            output=str(output),
            temp_dir=TEMP_DIR,
        )
        with output.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            fieldnames = reader.fieldnames
    finally:
        output.unlink(missing_ok=True)

    assert fieldnames == ["section", "value"]
    assert rows
    assert all(set(row) == {"section", "value"} for row in rows)


def test_file_result_mode_requires_output():
    with pytest.raises(InvalidInputError):
        compare([1], [2], mode="disk", result_mode="file")


def test_file_result_mode_requires_disk_or_auto():
    with pytest.raises(InvalidInputError):
        compare([1], [2], mode="memory", result_mode="file", output=str(FIXTURES / "never.jsonl"))


def test_auto_mode_uses_disk_for_file_result_mode():
    output = FIXTURES / "auto-file-result.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare(
            [1, 2],
            [2, 3],
            mode="auto",
            result_mode="file",
            output=str(output),
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert result.metadata["backend"] == "sqlite"
    assert result.metadata["auto_decision"]["reason"] == "result_mode='file'"
    assert {"section": "only_in_first", "value": 1} in rows


def test_cli_file_result_mode():
    output = FIXTURES / "cli-result-mode.jsonl"
    output.unlink(missing_ok=True)
    try:
        exit_code = main(
            [
                "compare",
                str(FIXTURES / "left.txt"),
                str(FIXTURES / "right.txt"),
                "--format",
                "txt",
                "--mode",
                "disk",
                "--result-mode",
                "file",
                "--output",
                str(output),
            ]
        )
        rows = _read_jsonl(output)
    finally:
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert {"section": "only_in_first", "value": "a"} in rows
    assert {"section": "only_in_second", "value": "c"} in rows
