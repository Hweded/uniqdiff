import json
from dataclasses import dataclass
from pathlib import Path

from uniqdiff import compare_file_schema, compare_schema, infer_schema
from uniqdiff.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_infer_schema_tracks_types_and_nullability():
    result = infer_schema(
        [
            {"id": 1, "name": "Ann", "score": 1.5},
            {"id": 2, "name": "", "score": None},
            {"id": 3, "score": 2.0},
        ]
    )

    assert result.row_count == 3
    assert result.columns["id"].types == ("int",)
    assert result.columns["name"].types == ("str",)
    assert result.columns["name"].nullable is True
    assert result.columns["name"].missing_count == 1
    assert result.columns["score"].types == ("float",)
    assert result.columns["score"].nullable is True


def test_compare_schema_reports_added_removed_type_and_nullable_changes():
    result = compare_schema(
        [
            {"id": 1, "name": "Ann", "age": 30, "legacy": "x"},
            {"id": 2, "name": "Bob", "age": 31, "legacy": "y"},
        ],
        [
            {"id": 1, "name": "Ann", "age": "30", "email": "a@example.test"},
            {"id": 2, "name": "", "age": "31", "email": "b@example.test"},
        ],
    )

    assert result.added_columns == ["email"]
    assert result.removed_columns == ["legacy"]
    assert result.type_changes == [{"column": "age", "left_types": ["int"], "right_types": ["str"]}]
    assert result.nullable_changes == [
        {"column": "name", "left_nullable": False, "right_nullable": True}
    ]
    assert result.has_changes is True


def test_compare_file_schema_reads_csv():
    left = FIXTURES / "schema-left.csv"
    right = FIXTURES / "schema-right.csv"
    left.write_text("id,name,age\n1,Ann,30\n2,Bob,31\n", encoding="utf-8")
    right.write_text("id,name,email\n1,Ann,a@example.test\n2,,b@example.test\n", encoding="utf-8")
    try:
        result = compare_file_schema(str(left), str(right), format="csv")
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert result.added_columns == ["email"]
    assert result.removed_columns == ["age"]
    assert result.nullable_changes == [
        {"column": "name", "left_nullable": False, "right_nullable": True}
    ]


def test_schema_diff_sampling_sets_warning():
    result = compare_schema(
        [{"id": 1}, {"id": 2, "later": True}],
        [{"id": 1}],
        sample_size=1,
    )

    assert result.left_schema.sampled is True
    assert result.warnings == ["Schema diff was inferred from sampled rows."]


def test_infer_schema_accepts_dataclass_and_object_rows():
    @dataclass
    class User:
        id: int
        name: str

    class Account:
        def __init__(self, id_value: int, active: bool) -> None:
            self.id = id_value
            self.active = active

    dataclass_schema = infer_schema([User(1, "Ann")])
    object_schema = infer_schema([Account(1, True)])

    assert dataclass_schema.columns["name"].types == ("str",)
    assert object_schema.columns["active"].types == ("bool",)


def test_schema_diff_can_treat_empty_string_as_string():
    result = compare_schema(
        [{"id": 1, "name": "Ann"}],
        [{"id": 1, "name": ""}],
        empty_string_null=False,
    )

    assert result.nullable_changes == []
    assert result.has_changes is False


def test_schema_diff_can_use_loose_numeric_types():
    strict = compare_schema(
        [{"id": 1, "amount": 1}],
        [{"id": 1, "amount": 1.5}],
    )
    loose = compare_schema(
        [{"id": 1, "amount": 1}],
        [{"id": 1, "amount": 1.5}],
        strict_numeric_types=False,
    )

    assert strict.type_changes == [
        {"column": "amount", "left_types": ["int"], "right_types": ["float"]}
    ]
    assert loose.type_changes == []
    assert loose.left_schema.columns["amount"].types == ("number",)


def test_cli_schema_diff_summary_and_fail_on_diff(capsys):
    left = FIXTURES / "cli-schema-left.csv"
    right = FIXTURES / "cli-schema-right.csv"
    output = FIXTURES / "cli-schema-output.json"
    left.write_text("id,name,age\n1,Ann,30\n", encoding="utf-8")
    right.write_text("id,name,email\n1,,ann@example.test\n", encoding="utf-8")
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "diff",
                str(left),
                str(right),
                "--format",
                "csv",
                "--schema-diff",
                "--summary",
                "--fail-on-diff",
                "--loose-numeric-types",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)
        output.unlink(missing_ok=True)

    assert exit_code == 1
    assert payload["equal"] is False
    assert payload["added_columns"] == ["email"]
    assert payload["removed_columns"] == ["age"]
    assert payload["nullable_change_count"] == 1
