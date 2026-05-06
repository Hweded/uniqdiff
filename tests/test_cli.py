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
