import json
from pathlib import Path

from uniqdiff import compare_fields, compare_fields_files

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
