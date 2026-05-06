import io
import json
from pathlib import Path

import pytest

from uniqdiff import InvalidInputError, compare, iter_compare_events, iter_event_rows
from uniqdiff.output import (
    EVENT_FORMAT,
    EVENT_FORMAT_VERSION,
    JsonlWriter,
    build_metadata_event,
    build_summary_event,
    compare_result_events,
    validate_event,
)

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_PATH = Path(__file__).parents[1] / "docs" / "schemas" / "uniqdiff-jsonl-1.0.schema.json"


def test_jsonl_writer_writes_one_valid_json_object_per_line():
    buffer = io.StringIO()
    writer = JsonlWriter(buffer)

    writer.write_event(build_metadata_event(key_columns=["id"]))
    writer.write_event({"type": "only_left", "key": {"id": "1"}})
    writer.write_event(build_summary_event(left_rows=1, only_left=1))

    rows = [json.loads(line) for line in buffer.getvalue().splitlines()]

    assert [row["type"] for row in rows] == ["metadata", "only_left", "summary"]
    assert rows[0]["format"] == EVENT_FORMAT
    assert rows[0]["format_version"] == EVENT_FORMAT_VERSION


@pytest.mark.parametrize(
    "event",
    [
        {"type": "field_change", "key": {"id": "1"}, "column": "price", "left": 10, "right": 12},
        {"type": "only_left", "key": {"id": "1"}},
        {"type": "only_right", "key": {"id": "2"}},
        {"type": "duplicate_key", "side": "left", "key": {"id": "3"}, "count": 2},
        {"type": "schema_change", "change": "column_added", "column": "discount"},
        {"type": "error", "code": "MISSING_KEY_COLUMN", "message": "missing id"},
        build_summary_event(),
    ],
)
def test_event_schema_accepts_required_fields(event):
    validate_event(event)


def test_event_schema_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_event({"type": "field_change", "key": {"id": "1"}, "column": "price"})


def test_compare_result_events_have_metadata_first_and_summary_last():
    result = compare(
        [{"id": "1"}, {"id": "2"}],
        [{"id": "2"}, {"id": "3"}],
        key="id",
        include_common=True,
    )

    events = list(compare_result_events(result, key="id", mode="compare"))

    assert events[0]["type"] == "metadata"
    assert events[-1]["type"] == "summary"
    assert {"type": "only_left", "key": {"id": "1"}} in events
    assert {"type": "only_right", "key": {"id": "3"}} in events
    assert events[-1]["common_rows"] == 1


def test_iter_compare_events_is_a_generator_contract():
    events = iter_compare_events([{"id": "1"}], [{"id": "2"}], key="id")

    first = next(events)
    rest = list(events)

    assert first["type"] == "metadata"
    assert rest[-1]["type"] == "summary"
    assert rest[-1]["only_left"] == 1
    assert rest[-1]["only_right"] == 1


def test_iter_event_rows_reads_and_validates_event_stream():
    output = FIXTURES / "event-reader-valid.jsonl"
    try:
        output.write_text(
            "\n".join(
                [
                    json.dumps(build_metadata_event(key_columns=["id"]), separators=(",", ":")),
                    json.dumps({"type": "only_left", "key": {"id": "1"}}, separators=(",", ":")),
                    json.dumps(
                        build_summary_event(left_rows=1, only_left=1),
                        separators=(",", ":"),
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        rows = list(iter_event_rows(output))
    finally:
        output.unlink(missing_ok=True)

    assert [row["type"] for row in rows] == ["metadata", "only_left", "summary"]


def test_iter_event_rows_rejects_invalid_envelope():
    output = FIXTURES / "event-reader-invalid-envelope.jsonl"
    try:
        output.write_text(
            json.dumps({"type": "only_left", "key": {"id": "1"}}, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(InvalidInputError, match="must start with metadata"):
            list(iter_event_rows(output))
    finally:
        output.unlink(missing_ok=True)


def test_iter_event_rows_rejects_missing_summary():
    output = FIXTURES / "event-reader-missing-summary.jsonl"
    try:
        output.write_text(
            json.dumps(build_metadata_event(), separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(InvalidInputError, match="must end with summary"):
            list(iter_event_rows(output))
    finally:
        output.unlink(missing_ok=True)


def test_json_schema_file_is_valid_json_and_documents_event_union():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["title"] == "uniqdiff.jsonl event"
    assert schema["$defs"]["metadata"]["properties"]["format"]["const"] == EVENT_FORMAT
    assert schema["$defs"]["metadata"]["properties"]["format_version"]["const"] == (
        EVENT_FORMAT_VERSION
    )
    assert len(schema["oneOf"]) == 9
