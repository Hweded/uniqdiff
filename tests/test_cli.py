import json
from pathlib import Path

import pytest

from uniqdiff.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_compare_outputs_json(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first"] == [{"id": "1", "name": "Ann"}]
    assert payload["only_in_second"] == [{"id": "3", "name": "Cara"}]
    assert payload["common"] == [{"id": "2", "name": "Bob"}]


def test_cli_compare_tsv_outputs_json(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.tsv"),
            str(FIXTURES / "right.tsv"),
            "--format",
            "tsv",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first"] == [{"id": "1", "name": "Ann"}]
    assert payload["only_in_second"] == [{"id": "3", "name": "Cara"}]


def test_cli_compare_csv_with_delimiter_outputs_json(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left_semicolon.csv"),
            str(FIXTURES / "right_semicolon.csv"),
            "--format",
            "csv",
            "--delimiter",
            ";",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first"] == [{"id": "1", "name": "Ann"}]
    assert payload["only_in_second"] == [{"id": "3", "name": "Cara"}]


def test_cli_compare_csv_without_header_outputs_json(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left_no_header.csv"),
            str(FIXTURES / "right_no_header.csv"),
            "--format",
            "csv",
            "--no-header",
            "--fieldnames",
            "id,name",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first"] == [{"id": "1", "name": "Ann"}]
    assert payload["only_in_second"] == [{"id": "3", "name": "Cara"}]


def test_cli_diff_writes_output_file():
    output = FIXTURES / "cli-output.json"
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "diff",
                str(FIXTURES / "left.txt"),
                str(FIXTURES / "right.txt"),
                "--format",
                "txt",
                "--output",
                str(output),
            ]
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
    finally:
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert payload["only_in_first"] == ["a"]
    assert payload["only_in_second"] == ["c"]
    assert payload["common"] is None


def test_cli_intersection_outputs_list(capsys):
    exit_code = main(
        [
            "intersection",
            str(FIXTURES / "left.jsonl"),
            str(FIXTURES / "right.jsonl"),
            "--format",
            "jsonl",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == [{"id": 2}]


def test_cli_duplicates_outputs_list(capsys):
    exit_code = main(
        [
            "duplicates",
            str(FIXTURES / "dupes.txt"),
            "--format",
            "txt",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == ["a", "b"]


def test_cli_compare_summary_outputs_counters(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--summary",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["equal"] is False
    assert payload["only_in_first_count"] == 1
    assert payload["only_in_second_count"] == 1
    assert payload["common_count"] == 1
    assert payload["backend"] == "memory"


def test_cli_field_diff_outputs_changed_fields(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--field-diff",
            "--columns",
            "name",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["rows"] == []
    assert payload["summary_by_column"] == {}
    assert payload["stats"]["changed_row_count"] == 0


def test_cli_field_diff_writes_jsonl_and_summary(capsys):
    left = FIXTURES / "cli-field-left.csv"
    right = FIXTURES / "cli-field-right.csv"
    output = FIXTURES / "cli-field-diff.jsonl"
    left.write_text("id,name,city\n1,Ann,Paris\n2,Bob,Berlin\n", encoding="utf-8")
    right.write_text("id,name,city\n1,Anne,Paris\n2,Bob,Rome\n", encoding="utf-8")
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "diff",
                str(left),
                str(right),
                "--format",
                "csv",
                "--key",
                "id",
                "--field-diff",
                "--exclude-columns",
                "city",
                "--max-rows",
                "1",
                "--output",
                str(output),
                "--summary",
                "--fail-on-diff",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)
        output.unlink(missing_ok=True)

    assert exit_code == 1
    assert payload["changed_row_count"] == 1
    assert payload["changed_field_count"] == 1
    assert payload["summary_by_column"] == {"name": 1}
    assert rows == [{"key": "1", "changes": [{"field": "name", "left": "Ann", "right": "Anne"}]}]


def test_cli_compare_writes_uniqdiff_jsonl_events_to_stdout(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--key",
            "id",
            "--format",
            "jsonl",
        ]
    )

    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 0
    assert rows[0]["type"] == "metadata"
    assert rows[0]["format"] == "uniqdiff.jsonl"
    assert rows[0]["format_version"] == "1.0"
    assert rows[-1]["type"] == "summary"
    assert {"type": "only_left", "key": {"id": "1"}} in rows
    assert {"type": "only_right", "key": {"id": "3"}} in rows


def test_cli_compare_writes_uniqdiff_jsonl_events_to_file():
    output = FIXTURES / "cli-events.jsonl"
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "compare",
                str(FIXTURES / "left.csv"),
                str(FIXTURES / "right.csv"),
                "--key",
                "id",
                "--format",
                "jsonl",
                "--output",
                str(output),
            ]
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert rows[0]["type"] == "metadata"
    assert rows[-1]["type"] == "summary"
    assert rows[-1]["only_left"] == 1
    assert rows[-1]["only_right"] == 1


def test_cli_compare_jsonl_events_can_use_disk_mode():
    output = FIXTURES / "cli-events-disk.jsonl"
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "compare",
                str(FIXTURES / "left.csv"),
                str(FIXTURES / "right.csv"),
                "--key",
                "id",
                "--format",
                "jsonl",
                "--mode",
                "disk",
                "--output",
                str(output),
            ]
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert rows[0]["type"] == "metadata"
    assert rows[-1]["type"] == "summary"
    assert {"type": "only_left", "key": {"id": "1"}} in rows
    assert {"type": "only_right", "key": {"id": "3"}} in rows


def test_cli_field_diff_jsonl_events_include_changed_fields(capsys):
    left = FIXTURES / "cli-event-field-left.csv"
    right = FIXTURES / "cli-event-field-right.csv"
    left.write_text("id,name,status\n1,Ann,old\n2,Bob,stable\n", encoding="utf-8")
    right.write_text("id,name,status\n1,Ann,new\n3,Cara,stable\n", encoding="utf-8")

    try:
        exit_code = main(
            [
                "diff",
                str(left),
                str(right),
                "--key",
                "id",
                "--format",
                "jsonl",
                "--field-diff",
                "--columns",
                "status",
            ]
        )
        rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)

    assert exit_code == 0
    assert [row["type"] for row in rows] == [
        "metadata",
        "only_left",
        "only_right",
        "row_changed",
        "field_change",
        "summary",
    ]
    assert rows[3] == {"type": "row_changed", "key": {"id": "1"}, "changed_columns": ["status"]}
    assert rows[4] == {
        "type": "field_change",
        "key": {"id": "1"},
        "column": "status",
        "left": "old",
        "right": "new",
    }


def test_cli_schema_diff_jsonl_events_to_file():
    left = FIXTURES / "cli-event-schema-left.csv"
    right = FIXTURES / "cli-event-schema-right.csv"
    output = FIXTURES / "cli-schema-events.jsonl"
    left.write_text("id,price\n1,10\n", encoding="utf-8")
    right.write_text("id,price,discount\n1,10.5,yes\n", encoding="utf-8")
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "diff",
                str(left),
                str(right),
                "--schema-diff",
                "--format",
                "jsonl",
                "--output",
                str(output),
            ]
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    finally:
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert rows[0]["type"] == "metadata"
    assert {"type": "schema_change", "change": "column_added", "column": "discount"} in rows
    assert rows[-1]["type"] == "summary"
    assert rows[-1]["schema_changes"] >= 1


def test_cli_fail_on_diff_returns_one_for_differences(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.txt"),
            str(FIXTURES / "right.txt"),
            "--format",
            "txt",
            "--summary",
            "--fail-on-diff",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["only_in_first_count"] == 1
    assert payload["only_in_second_count"] == 1


def test_cli_fail_on_diff_returns_zero_for_equal_files(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.txt"),
            str(FIXTURES / "left.txt"),
            "--format",
            "txt",
            "--summary",
            "--fail-on-diff",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["equal"] is True


def test_cli_duplicates_summary_and_fail_on_diff(capsys):
    exit_code = main(
        [
            "duplicates",
            str(FIXTURES / "dupes.txt"),
            "--format",
            "txt",
            "--summary",
            "--fail-on-diff",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload == {"duplicate_count": 2, "empty": False}


def test_cli_missing_file_returns_short_error(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "missing.txt"),
            str(FIXTURES / "right.txt"),
            "--format",
            "txt",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "uniqdiff: file not found:" in captured.err


def test_cli_field_diff_requires_key(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--field-diff",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "uniqdiff: --field-diff requires --key" in captured.err


def test_cli_schema_and_field_diff_are_mutually_exclusive(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--field-diff",
            "--schema-diff",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "--schema-diff cannot be combined with --field-diff" in captured.err


def test_cli_field_diff_output_requires_jsonl(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--field-diff",
            "--output",
            str(FIXTURES / "bad-field-output.json"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "--field-diff --output supports only .jsonl" in captured.err


def test_cli_schema_diff_output_requires_json(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--schema-diff",
            "--output",
            str(FIXTURES / "bad-schema-output.jsonl"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "--schema-diff --output supports only .json" in captured.err


def test_cli_result_mode_is_rejected_for_field_and_schema_modes(capsys):
    exit_code = main(
        [
            "diff",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--field-diff",
            "--result-mode",
            "file",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "--result-mode is not used with --field-diff or --schema-diff" in captured.err


def test_cli_compare_help_mentions_parquet(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["compare", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "parquet" in captured.out
    assert "--result-mode" in captured.out
    assert "--memory-limit" in captured.out


def test_cli_duplicates_help_hides_compare_only_options(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["duplicates", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "--result-mode" not in captured.out
    assert "--output" not in captured.out
    assert "--memory-limit" not in captured.out


def test_documented_cli_fixture_compare_summary_example(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.csv"),
            str(FIXTURES / "right.csv"),
            "--format",
            "csv",
            "--key",
            "id",
            "--summary",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first_count"] == 1
    assert payload["only_in_second_count"] == 1


def test_documented_cli_fixture_tsv_example(capsys):
    exit_code = main(
        [
            "compare",
            str(FIXTURES / "left.tsv"),
            str(FIXTURES / "right.tsv"),
            "--format",
            "tsv",
            "--key",
            "id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["only_in_first"] == [{"id": "1", "name": "Ann"}]


def test_documented_cli_fixture_diff_output_example():
    output = FIXTURES / "documented-cli-diff-output.json"
    output.unlink(missing_ok=True)

    try:
        exit_code = main(
            [
                "diff",
                str(FIXTURES / "left.txt"),
                str(FIXTURES / "right.txt"),
                "--format",
                "txt",
                "--output",
                str(output),
            ]
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
    finally:
        output.unlink(missing_ok=True)

    assert exit_code == 0
    assert payload["only_in_first"] == ["a"]
    assert payload["only_in_second"] == ["c"]


def test_documented_cli_fixture_duplicates_summary_example(capsys):
    exit_code = main(
        [
            "duplicates",
            str(FIXTURES / "dupes.txt"),
            "--format",
            "txt",
            "--summary",
            "--fail-on-diff",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload == {"duplicate_count": 2, "empty": False}


def test_readme_quick_start_commands_work_in_fixture_workspace(capsys):
    old = FIXTURES / "readme-old.csv"
    new = FIXTURES / "readme-new.csv"
    old.unlink(missing_ok=True)
    new.unlink(missing_ok=True)

    try:
        old.write_text(
            "id,name,status\n1,Alice,active\n2,Bob,pending\n3,Cara,active\n",
            encoding="utf-8",
        )
        new.write_text(
            "id,name,status\n2,Bob,active\n3,Cara,active\n4,Dana,pending\n",
            encoding="utf-8",
        )

        summary_exit = main(
            [
                "diff",
                str(old),
                str(new),
                "--format",
                "csv",
                "--key",
                "id",
                "--summary",
            ]
        )
        summary = json.loads(capsys.readouterr().out)

        field_exit = main(
            [
                "diff",
                str(old),
                str(new),
                "--format",
                "csv",
                "--key",
                "id",
                "--field-diff",
            ]
        )
        field_payload = json.loads(capsys.readouterr().out)

        schema_exit = main(
            [
                "diff",
                str(old),
                str(new),
                "--format",
                "csv",
                "--schema-diff",
                "--summary",
            ]
        )
        schema_summary = json.loads(capsys.readouterr().out)
    finally:
        old.unlink(missing_ok=True)
        new.unlink(missing_ok=True)

    assert summary_exit == 0
    assert summary["only_in_first_count"] == 1
    assert summary["only_in_second_count"] == 1
    assert summary["common_count"] == 2
    assert field_exit == 0
    assert field_payload["summary_by_column"] == {"status": 1}
    assert schema_exit == 0
    assert schema_summary["equal"] is True


def test_cli_docs_cover_documented_flags():
    docs = (Path(__file__).parents[1] / "docs" / "cli.md").read_text(encoding="utf-8")
    flags = {
        "--chunk-size",
        "--columns",
        "--delimiter",
        "--disk-limit",
        "--disk-strategy",
        "--encoding",
        "--fail-on-diff",
        "--fieldnames",
        "--format",
        "--include-duplicates",
        "--input-format",
        "--key",
        "--lower",
        "--field-diff",
        "--exclude-columns",
        "--max-rows",
        "--max-bytes",
        "--schema-diff",
        "--schema-sample-size",
        "--empty-string-not-null",
        "--loose-numeric-types",
        "--memory-limit",
        "--mode",
        "--no-header",
        "--no-strip",
        "--output",
        "--parquet-batch-size",
        "--partition-count",
        "--quotechar",
        "--remove-spaces",
        "--remove-special",
        "--result-mode",
        "--strip",
        "--summary",
        "--temp-dir",
    }

    missing = {flag for flag in flags if flag not in docs}

    assert missing == set()
