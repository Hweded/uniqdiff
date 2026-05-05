from __future__ import annotations

import json
import shutil
from pathlib import Path

from uniqrowdiff import diff_csv_by_key
from uniqrowdiff.cli import main


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    columns = ["id", "name", "status", "score", "updated_at"]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(row[column] for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_diff_csv_by_key_reports_changed_fields_and_presence():
    workspace = _workspace("presence")
    try:
        old_csv = workspace / "old.csv"
        new_csv = workspace / "new.csv"
        output = workspace / "changes.jsonl"
        _write_csv(
            old_csv,
            [
                {
                    "id": "1",
                    "name": "Ann",
                    "status": "active",
                    "score": "10",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "active",
                    "score": "20",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "active",
                    "score": "20",
                    "updated_at": "2026-05-01",
                },
                {
                    "id": "4",
                    "name": "Dana",
                    "status": "active",
                    "score": "40",
                    "updated_at": "2026-05-01",
                },
            ],
        )
        _write_csv(
            new_csv,
            [
                {
                    "id": "2",
                    "name": "Bob",
                    "status": "inactive",
                    "score": "25",
                    "updated_at": "2026-05-05",
                },
                {
                    "id": "3",
                    "name": "Cara",
                    "status": "active",
                    "score": "30",
                    "updated_at": "2026-05-05",
                },
                {
                    "id": "4",
                    "name": "Dana",
                    "status": "inactive",
                    "score": "41",
                    "updated_at": "2026-05-05",
                },
            ],
        )

        result = diff_csv_by_key(
            old_csv,
            new_csv,
            key="id",
            ignore_fields=("updated_at",),
            output=output,
        )

        assert result.summary.only_in_first == 1
        assert result.summary.only_in_second == 1
        assert result.summary.common == 2
        assert result.summary.duplicates_first == 1
        assert result.summary.changed_rows == 1
        assert result.summary.changed_fields == 2
        assert result.summary.skipped_duplicate_keys == 1
        assert [change.key for change in result.changes] == ["4"]
        assert {change.field for change in result.changes[0].changes} == {"score", "status"}
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        assert rows[0]["section"] == "changed"
        assert rows[0]["value"]["key"] == "4"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_cli_returns_failure_code_when_requested(capsys):
    workspace = _workspace("cli")
    try:
        old_csv = workspace / "old.csv"
        new_csv = workspace / "new.csv"
        _write_csv(
            old_csv,
            [
                {
                    "id": "1",
                    "name": "Ann",
                    "status": "active",
                    "score": "10",
                    "updated_at": "2026-05-01",
                }
            ],
        )
        _write_csv(
            new_csv,
            [
                {
                    "id": "1",
                    "name": "Ann",
                    "status": "inactive",
                    "score": "10",
                    "updated_at": "2026-05-01",
                }
            ],
        )

        exit_code = main(
            [
                str(old_csv),
                str(new_csv),
                "--key",
                "id",
                "--fail-on-changes",
            ]
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert '"changed_rows": 1' in captured.out
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _workspace(name: str) -> Path:
    path = Path.cwd() / ".tmp" / "uniqrowdiff_tests" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
