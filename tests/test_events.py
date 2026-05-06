import io
import json

import pytest

from uniqdiff import compare, iter_compare_events
from uniqdiff.output import (
    EVENT_FORMAT,
    EVENT_FORMAT_VERSION,
    JsonlWriter,
    build_metadata_event,
    build_summary_event,
    compare_result_events,
    validate_event,
)


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
