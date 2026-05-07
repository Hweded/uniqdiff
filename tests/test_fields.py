import json
from pathlib import Path

import pytest

from uniqdiff import (
    InvalidInputError,
    compare_fields,
    compare_fields_files,
    compare_fields_files_sorted,
    compare_fields_sorted,
    iter_field_diff_rows,
    iter_field_diff_sorted,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compare_fields_reports_changed_fields_and_summary():
    left = [
        {"id": 1, "name": "Ann", "city": "Paris"},
        {"id": 2, "name": "Bob", "city": "Berlin"},
    ]
    right = [
        {"id": 1, "name": "Anne", "city": "Paris"},
        {"id": 2, "name": "Bob", "city": "Rome"},
    ]

    result = compare_fields(left, right, key="id")

    assert result.rows == [
        {"key": 1, "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]},
        {"key": 2, "changes": [{"field": "city", "left": "Berlin", "right": "Rome"}]},
    ]
    assert result.summary_by_column == {"name": 1, "city": 1}
    assert result.stats.changed_row_count == 2
    assert result.stats.changed_field_count == 2


def test_compare_fields_supports_composite_dict_keys():
    result = compare_fields(
        [{"tenant": "a", "id": 1, "status": "old"}],
        [{"tenant": "a", "id": 1, "status": "new"}],
        key=("tenant", "id"),
        columns=("status",),
    )

    assert result.rows == [
        {"key": ("a", 1), "changes": [{"field": "status", "left": "old", "right": "new"}]}
    ]


def test_compare_fields_respects_column_filter_and_exclusions():
    left = [{"id": 1, "name": "Ann", "city": "Paris", "updated_at": "old"}]
    right = [{"id": 1, "name": "Anne", "city": "Rome", "updated_at": "new"}]

    result = compare_fields(
        left,
        right,
        key="id",
        columns=("name", "city", "updated_at"),
        exclude_columns=("updated_at",),
    )

    assert result.summary_by_column == {"city": 1, "name": 1}
    assert [change["field"] for change in result.rows[0]["changes"]] == ["city", "name"]


def test_compare_fields_streams_jsonl_and_applies_row_limit():
    output = FIXTURES / "field-diff.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare_fields(
            [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
            [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}],
            key="id",
            output=output,
            max_rows=1,
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        output.unlink(missing_ok=True)

    assert result.rows == []
    assert result.stats.changed_row_count == 2
    assert result.stats.emitted_row_count == 1
    assert result.stats.truncated is True
    assert rows == [{"key": 1, "changes": [{"field": "name", "left": "a", "right": "x"}]}]


def test_iter_field_diff_rows_reads_streamed_jsonl_lazily():
    output = FIXTURES / "field-diff-lazy.jsonl"
    output.unlink(missing_ok=True)
    try:
        compare_fields(
            [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
            [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}],
            key="id",
            output=output,
        )

        rows = list(iter_field_diff_rows(output))
    finally:
        output.unlink(missing_ok=True)

    assert rows == [
        {"key": 1, "changes": [{"field": "name", "left": "a", "right": "x"}]},
        {"key": 2, "changes": [{"field": "name", "left": "b", "right": "y"}]},
    ]


def test_compare_fields_streaming_respects_max_bytes():
    output = FIXTURES / "field-diff-max-bytes.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare_fields(
            [{"id": 1, "name": "a"}],
            [{"id": 1, "name": "x"}],
            key="id",
            output=output,
            max_bytes=1,
        )
        content = output.read_text(encoding="utf-8")
    finally:
        output.unlink(missing_ok=True)

    assert content == ""
    assert result.stats.changed_row_count == 1
    assert result.stats.emitted_row_count == 0
    assert result.stats.truncated is True


def test_compare_fields_files_reads_csv_and_filters_columns():
    left = FIXTURES / "field-left.csv"
    right = FIXTURES / "field-right.csv"
    left.write_text("id,name,city\n1,Ann,Paris\n2,Bob,Berlin\n", encoding="utf-8")
    right.write_text("id,name,city\n1,Anne,Paris\n2,Bob,Rome\n", encoding="utf-8")
    try:
        result = compare_fields_files(
            str(left),
            str(right),
            format="csv",
            key="id",
            columns=("name",),
        )
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.rows == [
        {"key": "1", "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]}
    ]
    assert result.summary_by_column == {"name": 1}


def test_compare_fields_reports_duplicate_keys_in_second_input():
    result = compare_fields(
        [{"id": 1, "name": "Ann"}],
        [{"id": 1, "name": "Anne"}, {"id": 1, "name": "Annie"}],
        key="id",
    )

    assert result.rows == [
        {"key": 1, "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]}
    ]
    assert result.metadata["duplicate_second_key_count"] == 1
    assert result.warnings == [
        "Duplicate keys were found in the second input; only the first row per key was used."
    ]


def test_iter_field_diff_sorted_streams_changes_without_indexing():
    rows = iter_field_diff_sorted(
        [
            {"id": 1, "name": "Ann", "city": "Paris"},
            {"id": 2, "name": "Bob", "city": "Berlin"},
            {"id": 4, "name": "Dana", "city": "Rome"},
        ],
        [
            {"id": 1, "name": "Anne", "city": "Paris"},
            {"id": 3, "name": "Cara", "city": "Paris"},
            {"id": 4, "name": "Dana", "city": "Milan"},
        ],
        key="id",
    )

    assert list(rows) == [
        {"key": 1, "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]},
        {"key": 4, "changes": [{"field": "city", "left": "Rome", "right": "Milan"}]},
    ]


def test_iter_field_diff_sorted_respects_columns_and_exclusions():
    rows = iter_field_diff_sorted(
        [{"id": 1, "name": "Ann", "city": "Paris"}],
        [{"id": 1, "name": "Anne", "city": "Rome"}],
        key="id",
        columns=("name", "city"),
        exclude_columns=("city",),
    )

    assert list(rows) == [
        {"key": 1, "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]}
    ]


def test_iter_field_diff_sorted_validates_key_order():
    rows = iter_field_diff_sorted(
        [{"id": 2, "name": "Bob"}, {"id": 1, "name": "Ann"}],
        [{"id": 1, "name": "Anne"}],
        key="id",
    )

    with pytest.raises(InvalidInputError, match="not sorted by key"):
        list(rows)


def test_compare_fields_sorted_returns_result_and_summary():
    result = compare_fields_sorted(
        [
            {"id": 1, "name": "Ann", "city": "Paris"},
            {"id": 2, "name": "Bob", "city": "Berlin"},
        ],
        [
            {"id": 1, "name": "Anne", "city": "Paris"},
            {"id": 2, "name": "Bob", "city": "Rome"},
        ],
        key="id",
    )

    assert result.rows == [
        {"key": 1, "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]},
        {"key": 2, "changes": [{"field": "city", "left": "Berlin", "right": "Rome"}]},
    ]
    assert result.summary_by_column == {"name": 1, "city": 1}
    assert result.stats.changed_row_count == 2
    assert result.stats.emitted_row_count == 2
    assert result.metadata["sorted_input"] is True
    assert result.warnings == [
        "Sorted field diff streams changed rows and does not materialize full input row counts."
    ]


def test_compare_fields_sorted_streams_jsonl_and_limits_rows():
    output = FIXTURES / "field-diff-sorted.jsonl"
    output.unlink(missing_ok=True)
    try:
        result = compare_fields_sorted(
            [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
            [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}],
            key="id",
            output=output,
            max_rows=1,
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        output.unlink(missing_ok=True)

    assert result.rows == []
    assert result.stats.changed_row_count == 2
    assert result.stats.emitted_row_count == 1
    assert result.stats.truncated is True
    assert rows == [{"key": 1, "changes": [{"field": "name", "left": "a", "right": "x"}]}]


def test_compare_fields_files_sorted_reads_csv():
    left = FIXTURES / "field-sorted-left.csv"
    right = FIXTURES / "field-sorted-right.csv"
    left.write_text("id,name\n1,Ann\n2,Bob\n", encoding="utf-8")
    right.write_text("id,name\n1,Anne\n2,Bob\n", encoding="utf-8")
    try:
        result = compare_fields_files_sorted(
            str(left),
            str(right),
            format="csv",
            key="id",
        )
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.rows == [
        {"key": "1", "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]}
    ]
