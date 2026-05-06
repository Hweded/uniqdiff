"""Streaming output helpers."""

from uniqdiff.output.events import (
    EVENT_FORMAT,
    EVENT_FORMAT_VERSION,
    Event,
    EventSummary,
    build_metadata_event,
    build_summary_event,
    compare_result_events,
    event_key,
    field_diff_file_events,
    field_diff_result_events,
    field_diff_row_events,
    iter_event_rows,
    schema_diff_result_events,
    summarize_event_file,
    summarize_events,
    validate_event,
)
from uniqdiff.output.jsonl import JsonlWriter, write_jsonl_events
from uniqdiff.output.result_files import (
    StreamingResultWriter,
    _json_dumps,
    ensure_result_mode,
    iter_result_rows,
    iter_result_values,
)

__all__ = [
    "EVENT_FORMAT",
    "EVENT_FORMAT_VERSION",
    "Event",
    "EventSummary",
    "JsonlWriter",
    "StreamingResultWriter",
    "_json_dumps",
    "build_metadata_event",
    "build_summary_event",
    "compare_result_events",
    "ensure_result_mode",
    "event_key",
    "field_diff_file_events",
    "field_diff_row_events",
    "field_diff_result_events",
    "iter_event_rows",
    "iter_result_rows",
    "iter_result_values",
    "schema_diff_result_events",
    "summarize_event_file",
    "summarize_events",
    "validate_event",
    "write_jsonl_events",
]
