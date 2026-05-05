import shutil
from pathlib import Path

import pytest

from uniqdiff import (
    InvalidInputError,
    compare_sorted_iter,
    iter_result_rows,
    iter_sorted_diff,
    write_sorted_diff,
    write_sorted_diff_file,
)


def test_iter_sorted_diff_streams_unique_rows():
    rows = list(iter_sorted_diff([1, 2, 4], [2, 3, 4], include_common=True))

    assert rows == [
        {"section": "only_in_first", "value": 1},
        {"section": "common", "value": 2},
        {"section": "only_in_second", "value": 3},
        {"section": "common", "value": 4},
    ]


def test_iter_sorted_diff_supports_keyed_rows_and_duplicates():
    left = [
        {"id": 1, "name": "Ann"},
        {"id": 2, "name": "Bob"},
        {"id": 2, "name": "Bob duplicate"},
        {"id": 4, "name": "Dana"},
    ]
    right = [
        {"id": 2, "name": "Bob new"},
        {"id": 3, "name": "Cara"},
        {"id": 3, "name": "Cara duplicate"},
        {"id": 4, "name": "Dana"},
    ]

    rows = list(
        iter_sorted_diff(
            left,
            right,
            key="id",
            include_common=True,
            include_duplicates=True,
        )
    )

    assert rows == [
        {"section": "only_in_first", "value": {"id": 1, "name": "Ann"}},
        {"section": "common", "value": {"id": 2, "name": "Bob"}},
        {"section": "duplicates_first", "value": {"id": 2, "name": "Bob duplicate"}},
        {"section": "only_in_second", "value": {"id": 3, "name": "Cara"}},
        {"section": "duplicates_second", "value": {"id": 3, "name": "Cara duplicate"}},
        {"section": "common", "value": {"id": 4, "name": "Dana"}},
    ]


def test_iter_sorted_diff_rejects_unsorted_input_by_default():
    with pytest.raises(InvalidInputError, match="sorted"):
        list(iter_sorted_diff([2, 1], [1, 2]))


def test_iter_sorted_diff_can_skip_sorted_validation():
    rows = list(iter_sorted_diff([1, 2], [2, 3], include_common=True, validate_sorted=False))

    assert rows == [
        {"section": "only_in_first", "value": 1},
        {"section": "common", "value": 2},
        {"section": "only_in_second", "value": 3},
    ]


def test_iter_sorted_diff_rejects_unorderable_tokens():
    with pytest.raises(InvalidInputError, match="orderable"):
        list(iter_sorted_diff([object()], [object()]))


def test_compare_sorted_iter_wraps_streaming_diff():
    rows = list(
        compare_sorted_iter(
            [{"id": 1}, {"id": 2}],
            [{"id": 2}, {"id": 3}],
            key="id",
            include_common=True,
        )
    )

    assert rows == [
        {"section": "only_in_first", "value": {"id": 1}},
        {"section": "common", "value": {"id": 2}},
        {"section": "only_in_second", "value": {"id": 3}},
    ]


def test_write_sorted_diff_writes_jsonl():
    workspace = _workspace("jsonl")
    try:
        output = workspace / "sorted-diff.jsonl"

        count = write_sorted_diff(
            [{"id": 1}, {"id": 2}],
            [{"id": 2}, {"id": 3}],
            str(output),
            key="id",
            include_common=True,
        )

        assert count == 3
        assert list(iter_result_rows(output)) == [
            {"section": "only_in_first", "value": {"id": 1}},
            {"section": "common", "value": {"id": 2}},
            {"section": "only_in_second", "value": {"id": 3}},
        ]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_write_sorted_diff_file_writes_csv():
    workspace = _workspace("csv")
    try:
        output = workspace / "sorted-diff.csv"

        count = write_sorted_diff_file(
            [1, 2, 2],
            [2, 3, 3],
            str(output),
            include_common=True,
            include_duplicates=True,
        )

        assert count == 5
        assert list(iter_result_rows(output)) == [
            {"section": "only_in_first", "value": 1},
            {"section": "common", "value": 2},
            {"section": "duplicates_first", "value": 2},
            {"section": "only_in_second", "value": 3},
            {"section": "duplicates_second", "value": 3},
        ]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _workspace(name: str) -> Path:
    path = Path.cwd() / ".tmp" / "streaming_tests" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
