import io
import json
from pathlib import Path

import pytest

from uniqdiff import (
    EventSummary,
    InvalidInputError,
    compare,
    iter_compare_events,
    iter_event_rows,
    iter_field_diff_events,
    iter_sorted_field_diff_events,
    summarize_event_file,
    summarize_events,
)
from uniqdiff._version import __version__
from uniqdiff.output import (
    EVENT_FORMAT,
    EVENT_FORMAT_VERSION,
    JsonlWriter,
    build_metadata_event,
    build_summary_event,
    compare_result_events,
    field_diff_file_events,
    field_diff_row_events,
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
    assert rows[0]["tool_version"] == __version__


def test_jsonl_writer_buffers_and_flushes_on_close():
    buffer = io.StringIO()
    writer = JsonlWriter(buffer, buffer_size=10)

    writer.write_event(build_metadata_event(key_columns=["id"]))
    assert buffer.getvalue() == ""

    writer.close()
    rows = [json.loads(line) for line in buffer.getvalue().splitlines()]
    assert rows[0]["type"] == "metadata"


def test_jsonl_writer_limits_data_events_but_preserves_envelope():
    buffer = io.StringIO()
    writer = JsonlWriter(buffer, max_output_rows=1)

    writer.write_event(build_metadata_event(key_columns=["id"]))
    assert writer.write_event({"type": "only_left", "key": {"id": "1"}}) is True
    assert writer.write_event({"type": "only_right", "key": {"id": "2"}}) is False
    writer.write_event(build_summary_event(left_rows=2, only_left=1, only_right=1))
    writer.close()

    rows = [json.loads(line) for line in buffer.getvalue().splitlines()]
    assert [row["type"] for row in rows] == ["metadata", "only_left", "summary"]
    assert rows[-1]["output_truncated"] is True
    assert rows[-1]["emitted_events"] == 1
    assert rows[-1]["skipped_events"] == 1


def test_jsonl_writer_byte_limit_counts_data_events_only():
    buffer = io.StringIO()
    writer = JsonlWriter(buffer, max_output_bytes=1)

    writer.write_event(build_metadata_event(key_columns=["id"]))
    assert writer.write_event({"type": "only_left", "key": {"id": "1"}}) is False
    writer.write_event(build_summary_event(left_rows=1, only_left=1))
    writer.close()

    rows = [json.loads(line) for line in buffer.getvalue().splitlines()]
    assert [row["type"] for row in rows] == ["metadata", "summary"]
    assert rows[-1]["output_truncated"] is True
    assert rows[-1]["skipped_events"] == 1


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


def test_field_diff_row_events_convert_changed_rows():
    events = list(
        field_diff_row_events(
            [
                {
                    "key": "1",
                    "changes": [{"field": "status", "left": "old", "right": "new"}],
                }
            ],
            key_columns=["id"],
        )
    )

    assert events == [
        {"type": "row_changed", "key": {"id": "1"}, "changed_columns": ["status"]},
        {
            "type": "field_change",
            "key": {"id": "1"},
            "column": "status",
            "left": "old",
            "right": "new",
        },
    ]


def test_field_diff_file_events_read_rows_lazily():
    output = FIXTURES / "event-field-diff-rows.jsonl"
    try:
        output.write_text(
            json.dumps(
                {
                    "key": "1",
                    "changes": [{"field": "price", "left": 10, "right": 12}],
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        events = list(field_diff_file_events(output, key_columns=["id"]))
    finally:
        output.unlink(missing_ok=True)

    assert events[0] == {"type": "row_changed", "key": {"id": "1"}, "changed_columns": ["price"]}
    assert events[1]["type"] == "field_change"
    assert events[1]["column"] == "price"


def test_iter_compare_events_is_a_generator_contract():
    events = iter_compare_events([{"id": "1"}], [{"id": "2"}], key="id")

    first = next(events)
    rest = list(events)

    assert first["type"] == "metadata"
    assert rest[-1]["type"] == "summary"
    assert rest[-1]["only_left"] == 1
    assert rest[-1]["only_right"] == 1


def test_iter_field_diff_events_yields_metadata_changes_and_summary():
    events = list(
        iter_field_diff_events(
            [{"id": "1", "status": "old"}],
            [{"id": "1", "status": "new"}],
            key="id",
            columns=("status",),
        )
    )

    assert [event["type"] for event in events] == [
        "metadata",
        "row_changed",
        "field_change",
        "summary",
    ]
    assert events[0]["mode"] == "field_diff"
    assert events[0]["compared_columns"] == ["status"]
    assert events[-1]["changed_rows"] == 1
    assert events[-1]["changed_fields"] == 1


def test_iter_sorted_field_diff_events_streams_sorted_inputs():
    events = iter_sorted_field_diff_events(
        [{"id": "1", "status": "old"}, {"id": "2", "status": "same"}],
        [{"id": "1", "status": "new"}, {"id": "2", "status": "same"}],
        key="id",
        columns=("status",),
    )

    first = next(events)
    rest = list(events)

    assert first["type"] == "metadata"
    assert first["compared_columns"] == ["status"]
    assert rest[0]["type"] == "row_changed"
    assert rest[-1]["type"] == "summary"
    assert rest[-1]["changed_rows"] == 1


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


def test_event_summary_observes_events_incrementally():
    summary = EventSummary()

    summary.observe({"type": "only_left", "key": {"id": "1"}})
    summary.observe({"type": "only_right", "key": {"id": "2"}})
    summary.observe({"type": "row_changed", "key": {"id": "3"}, "changed_columns": ["price"]})
    summary.observe(
        {"type": "field_change", "key": {"id": "3"}, "column": "price", "left": 10, "right": 12}
    )
    summary.observe({"type": "duplicate_key", "side": "left", "key": {"id": "4"}, "count": 2})
    summary.observe({"type": "schema_change", "change": "column_added", "column": "discount"})

    event = summary.to_event()

    assert event["only_left"] == 1
    assert event["only_right"] == 1
    assert event["changed_rows"] == 1
    assert event["changed_fields"] == 1
    assert event["duplicate_keys_left"] == 1
    assert event["schema_changes"] == 1
    assert event["event_count"] == 6


def test_summarize_events_can_recompute_without_materializing():
    events = iter(
        [
            build_metadata_event(key_columns=["id"]),
            {"type": "only_left", "key": {"id": "1"}},
            {"type": "only_right", "key": {"id": "2"}},
            build_summary_event(left_rows=10, right_rows=10, only_left=99),
        ]
    )

    summary = summarize_events(events, prefer_stream_summary=False)

    assert summary["left_rows"] == 0
    assert summary["only_left"] == 1
    assert summary["only_right"] == 1
    assert summary["event_count"] == 3


def test_summarize_events_prefers_stream_summary_by_default():
    summary = summarize_events(
        [
            build_metadata_event(key_columns=["id"]),
            {"type": "only_left", "key": {"id": "1"}},
            build_summary_event(left_rows=10, right_rows=10, only_left=99),
        ]
    )

    assert summary["left_rows"] == 10
    assert summary["only_left"] == 99


def test_summarize_event_file_reads_lazily():
    output = FIXTURES / "event-summary-valid.jsonl"
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
        summary = summarize_event_file(output)
        recomputed = summarize_event_file(output, prefer_stream_summary=False)
    finally:
        output.unlink(missing_ok=True)

    assert summary["left_rows"] == 1
    assert recomputed["only_left"] == 1
    assert recomputed["event_count"] == 2
