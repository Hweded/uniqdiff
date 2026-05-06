"""Stable JSONL event stream schema."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, Optional, Union

from uniqdiff._typing import KeySpec
from uniqdiff.exceptions import InvalidInputError
from uniqdiff.result import CompareResult
from uniqdiff.tokens import extract_key

EVENT_FORMAT = "uniqdiff.jsonl"
EVENT_FORMAT_VERSION = "1.0"

EventType = Literal[
    "metadata",
    "only_left",
    "only_right",
    "row_changed",
    "field_change",
    "duplicate_key",
    "schema_change",
    "error",
    "summary",
]
Event = Mapping[str, Any]


@dataclass
class EventSummary:
    """Incremental counters derived from a `uniqdiff.jsonl` event stream."""

    left_rows: int = 0
    right_rows: int = 0
    common_rows: int = 0
    only_left: int = 0
    only_right: int = 0
    changed_rows: int = 0
    changed_fields: int = 0
    duplicate_keys_left: int = 0
    duplicate_keys_right: int = 0
    schema_changes: int = 0
    error_count: int = 0
    event_count: int = 0

    def observe(self, event: Mapping[str, Any]) -> None:
        """Update counters from one event without retaining the event."""

        validate_event(event)
        self.event_count += 1
        event_type = event["type"]
        if event_type == "only_left":
            self.only_left += 1
        elif event_type == "only_right":
            self.only_right += 1
        elif event_type == "row_changed":
            self.changed_rows += 1
        elif event_type == "field_change":
            self.changed_fields += 1
        elif event_type == "duplicate_key":
            side = event["side"]
            if side == "left":
                self.duplicate_keys_left += 1
            elif side == "right":
                self.duplicate_keys_right += 1
        elif event_type == "schema_change":
            self.schema_changes += 1
        elif event_type == "error":
            self.error_count += 1

    def to_event(self) -> dict[str, Any]:
        """Return a `summary` event for the observed stream."""

        event = build_summary_event(
            left_rows=self.left_rows,
            right_rows=self.right_rows,
            common_rows=self.common_rows,
            only_left=self.only_left,
            only_right=self.only_right,
            changed_rows=self.changed_rows,
            changed_fields=self.changed_fields,
            duplicate_keys_left=self.duplicate_keys_left,
            duplicate_keys_right=self.duplicate_keys_right,
            schema_changes=self.schema_changes,
        )
        if self.error_count:
            event["error_count"] = self.error_count
        event["event_count"] = self.event_count
        return event


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tool_version() -> str:
    try:
        return version("uniqdiff")
    except PackageNotFoundError:
        return "0.0.0"


@dataclass(frozen=True)
class MetadataEvent:
    type: Literal["metadata"] = "metadata"
    format: str = EVENT_FORMAT
    format_version: str = EVENT_FORMAT_VERSION
    tool: str = "uniqdiff"
    tool_version: str = field(default_factory=_tool_version)
    mode: str = "diff"
    key_columns: list[str] = field(default_factory=list)
    compared_columns: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "format": self.format,
            "format_version": self.format_version,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "mode": self.mode,
            "key_columns": self.key_columns,
            "compared_columns": self.compared_columns,
            "created_at": self.created_at,
        }


def build_metadata_event(
    *,
    mode: str = "diff",
    key_columns: Optional[Sequence[str]] = None,
    compared_columns: Optional[Sequence[str]] = None,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Build the first event in a JSONL event stream."""

    event = MetadataEvent(
        mode=mode,
        key_columns=list(key_columns or ()),
        compared_columns=list(compared_columns or ()),
        created_at=created_at or _utc_now(),
    ).to_dict()
    validate_event(event)
    return event


def build_summary_event(
    *,
    left_rows: int = 0,
    right_rows: int = 0,
    common_rows: int = 0,
    only_left: int = 0,
    only_right: int = 0,
    changed_rows: int = 0,
    changed_fields: int = 0,
    duplicate_keys_left: int = 0,
    duplicate_keys_right: int = 0,
    schema_changes: int = 0,
    elapsed_seconds: Optional[float] = None,
    peak_mb: Optional[float] = None,
) -> dict[str, Any]:
    """Build the last event in a JSONL event stream."""

    event: dict[str, Any] = {
        "type": "summary",
        "left_rows": left_rows,
        "right_rows": right_rows,
        "common_rows": common_rows,
        "only_left": only_left,
        "only_right": only_right,
        "changed_rows": changed_rows,
        "changed_fields": changed_fields,
        "duplicate_keys_left": duplicate_keys_left,
        "duplicate_keys_right": duplicate_keys_right,
        "schema_changes": schema_changes,
    }
    if elapsed_seconds is not None:
        event["elapsed_seconds"] = elapsed_seconds
    if peak_mb is not None:
        event["peak_mb"] = peak_mb
    validate_event(event)
    return event


def compare_result_events(
    result: CompareResult,
    *,
    key: KeySpec = None,
    mode: str = "diff",
    key_columns: Optional[Sequence[str]] = None,
    compared_columns: Optional[Sequence[str]] = None,
    created_at: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """Yield metadata, compare events, and summary for a `CompareResult`."""

    columns = list(key_columns) if key_columns is not None else _key_columns(key)
    yield build_metadata_event(
        mode=mode,
        key_columns=columns,
        compared_columns=compared_columns,
        created_at=created_at,
    )

    for row in result.only_in_first:
        yield _event("only_left", key=event_key(row, key=key, key_columns=columns))
    for row in result.only_in_second:
        yield _event("only_right", key=event_key(row, key=key, key_columns=columns))
    yield from _duplicate_events("left", result.duplicates_first, key=key, key_columns=columns)
    yield from _duplicate_events("right", result.duplicates_second, key=key, key_columns=columns)

    stats = result.stats
    yield build_summary_event(
        left_rows=stats.first_count,
        right_rows=stats.second_count,
        common_rows=stats.common_count,
        only_left=stats.only_in_first_count,
        only_right=stats.only_in_second_count,
        duplicate_keys_left=stats.duplicate_first_count,
        duplicate_keys_right=stats.duplicate_second_count,
    )


def field_diff_result_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    stats: Mapping[str, Any],
    summary_by_column: Optional[Mapping[str, int]] = None,
    key_columns: Optional[Sequence[str]] = None,
    compared_columns: Optional[Sequence[str]] = None,
    mode: str = "field_diff",
    created_at: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """Yield metadata, field-diff events, and summary for changed-row rows."""

    yield build_metadata_event(
        mode=mode,
        key_columns=key_columns,
        compared_columns=compared_columns,
        created_at=created_at,
    )

    changed_rows = 0
    changed_fields = 0
    for event in field_diff_row_events(rows, key_columns=key_columns):
        if event["type"] == "row_changed":
            changed_rows += 1
        elif event["type"] == "field_change":
            changed_fields += 1
        yield event

    yield build_summary_event(
        left_rows=int(stats.get("first_count", 0)),
        right_rows=int(stats.get("second_count", 0)),
        common_rows=int(stats.get("compared_count", 0)),
        changed_rows=int(stats.get("changed_row_count", changed_rows)),
        changed_fields=int(stats.get("changed_field_count", changed_fields)),
    )


def field_diff_row_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    key_columns: Optional[Sequence[str]] = None,
) -> Iterator[dict[str, Any]]:
    """Yield row_changed and field_change events from field-diff rows.

    Input rows use the stable field-diff JSONL row shape:
    `{"key": ..., "changes": [{"field": ..., "left": ..., "right": ...}]}`.
    This helper intentionally does not emit metadata or summary events, so callers
    can compose it with compare/presence/schema events.
    """

    for row in rows:
        key_value = event_key(row.get("key"), key_columns=key_columns)
        changes = list(row.get("changes", ()))
        changed_columns = [str(change["field"]) for change in changes if "field" in change]
        if changed_columns:
            yield _event("row_changed", key=key_value, changed_columns=changed_columns)
        for change in changes:
            yield _event(
                "field_change",
                key=key_value,
                column=change["field"],
                left=change.get("left"),
                right=change.get("right"),
            )


def field_diff_file_events(
    output: Union[str, os.PathLike[str]],
    *,
    key_columns: Optional[Sequence[str]] = None,
) -> Iterator[dict[str, Any]]:
    """Yield field-diff events lazily from a field-diff JSONL row file."""

    output_path = Path(output)
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise InvalidInputError("field diff JSONL row must be an object")
            yield from field_diff_row_events([row], key_columns=key_columns)


def schema_diff_result_events(
    result: Any,
    *,
    mode: str = "schema_diff",
    created_at: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """Yield metadata, schema change events, and summary for a schema diff result."""

    yield build_metadata_event(mode=mode, created_at=created_at)

    schema_changes = 0
    for column in result.added_columns:
        schema_changes += 1
        yield _event("schema_change", change="column_added", column=column)
    for column in result.removed_columns:
        schema_changes += 1
        yield _event("schema_change", change="column_removed", column=column)
    for change in result.type_changes:
        schema_changes += 1
        yield _event(
            "schema_change",
            change="type_changed",
            column=change["column"],
            left_type=_format_types(change.get("left_types", ())),
            right_type=_format_types(change.get("right_types", ())),
        )
    for change in result.nullable_changes:
        schema_changes += 1
        yield _event(
            "schema_change",
            change="nullable_changed",
            column=change["column"],
            left_nullable=change.get("left_nullable"),
            right_nullable=change.get("right_nullable"),
        )

    yield build_summary_event(
        left_rows=result.left_schema.row_count,
        right_rows=result.right_schema.row_count,
        schema_changes=schema_changes,
    )


def event_key(
    value: Any,
    *,
    key: KeySpec = None,
    key_columns: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Return the canonical JSONL event key object."""

    columns = list(key_columns or _key_columns(key))
    token = extract_key(value, key) if key is not None else value
    if columns:
        if len(columns) == 1:
            return {columns[0]: token}
        if isinstance(token, (tuple, list)):
            return {column: token[index] for index, column in enumerate(columns)}
    return {"value": token}


def validate_event(event: Mapping[str, Any]) -> None:
    """Validate the required fields for one JSONL event."""

    event_type = event.get("type")
    if event_type not in _REQUIRED_FIELDS:
        raise ValueError(f"unsupported event type: {event_type!r}")
    missing = [field for field in _REQUIRED_FIELDS[event_type] if field not in event]
    if missing:
        raise ValueError(f"{event_type} event is missing required fields: {missing}")
    if event_type == "metadata":
        if event.get("format") != EVENT_FORMAT:
            raise ValueError("metadata event has unsupported format")
        if event.get("format_version") != EVENT_FORMAT_VERSION:
            raise ValueError("metadata event has unsupported format_version")


def iter_event_rows(
    output: Union[str, os.PathLike[str]],
    *,
    validate_sequence: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield `uniqdiff.jsonl` events lazily from a JSONL event stream.

    Each yielded object is validated for required fields. When
    `validate_sequence=True`, the reader also enforces the stream envelope:
    the first event must be `metadata` and the last event must be `summary`.
    """

    output_path = Path(output)
    seen_any = False
    last_type: Optional[str] = None
    with output_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InvalidInputError(
                    f"Invalid JSONL event at line {line_number} in {output_path}: {exc.msg}"
                ) from exc
            if not isinstance(event, dict):
                raise InvalidInputError(
                    f"JSONL event at line {line_number} in {output_path} must be an object"
                )
            try:
                validate_event(event)
            except ValueError as exc:
                raise InvalidInputError(
                    f"Invalid JSONL event at line {line_number} in {output_path}: {exc}"
                ) from exc
            if validate_sequence and not seen_any and event["type"] != "metadata":
                raise InvalidInputError("uniqdiff.jsonl stream must start with metadata")
            seen_any = True
            last_type = str(event["type"])
            yield event
    if validate_sequence:
        if not seen_any:
            raise InvalidInputError("uniqdiff.jsonl stream is empty")
        if last_type != "summary":
            raise InvalidInputError("uniqdiff.jsonl stream must end with summary")


def summarize_events(
    events: Iterable[Mapping[str, Any]],
    *,
    prefer_stream_summary: bool = True,
) -> dict[str, Any]:
    """Summarize an event iterable without storing the full stream.

    When a `summary` event is present and `prefer_stream_summary=True`, that
    authoritative stream summary is returned. Set `prefer_stream_summary=False` to
    recompute counters only from observed non-summary events.
    """

    computed = EventSummary()
    stream_summary: Optional[dict[str, Any]] = None
    for event in events:
        validate_event(event)
        if event["type"] == "summary":
            stream_summary = dict(event)
            continue
        computed.observe(event)
    if prefer_stream_summary and stream_summary is not None:
        return stream_summary
    return computed.to_event()


def summarize_event_file(
    output: Union[str, os.PathLike[str]],
    *,
    prefer_stream_summary: bool = True,
    validate_sequence: bool = True,
) -> dict[str, Any]:
    """Read and summarize a `uniqdiff.jsonl` file lazily."""

    return summarize_events(
        iter_event_rows(output, validate_sequence=validate_sequence),
        prefer_stream_summary=prefer_stream_summary,
    )


def _event(event_type: EventType, **values: Any) -> dict[str, Any]:
    event = {"type": event_type, **values}
    validate_event(event)
    return event


def _duplicate_events(
    side: Literal["left", "right"],
    rows: Optional[Iterable[Any]],
    *,
    key: KeySpec,
    key_columns: Sequence[str],
) -> Iterator[dict[str, Any]]:
    if not rows:
        return
    grouped: Counter[tuple[tuple[str, Any], ...]] = Counter()
    keys: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}
    for row in rows:
        key_value = event_key(row, key=key, key_columns=key_columns)
        stable_key = tuple(sorted(key_value.items()))
        grouped[stable_key] += 1
        keys[stable_key] = key_value
    for stable_key, duplicate_count in grouped.items():
        yield _event(
            "duplicate_key",
            side=side,
            key=keys[stable_key],
            count=duplicate_count + 1,
        )


def _key_columns(key: KeySpec) -> list[str]:
    if isinstance(key, str):
        return [key]
    if isinstance(key, (tuple, list)) and all(isinstance(part, str) for part in key):
        return list(key)
    return []


def _format_types(types: Any) -> Any:
    if isinstance(types, list) and len(types) == 1:
        return types[0]
    if isinstance(types, tuple) and len(types) == 1:
        return types[0]
    return types


_REQUIRED_FIELDS: dict[Union[str, Any], tuple[str, ...]] = {
    "metadata": (
        "type",
        "format",
        "format_version",
        "tool",
        "tool_version",
        "mode",
        "key_columns",
        "compared_columns",
        "created_at",
    ),
    "only_left": ("type", "key"),
    "only_right": ("type", "key"),
    "row_changed": ("type", "key", "changed_columns"),
    "field_change": ("type", "key", "column", "left", "right"),
    "duplicate_key": ("type", "side", "key", "count"),
    "schema_change": ("type", "change", "column"),
    "error": ("type", "code", "message"),
    "summary": (
        "type",
        "left_rows",
        "right_rows",
        "common_rows",
        "only_left",
        "only_right",
        "changed_rows",
        "changed_fields",
        "duplicate_keys_left",
        "duplicate_keys_right",
        "schema_changes",
    ),
}
