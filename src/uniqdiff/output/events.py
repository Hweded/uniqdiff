"""Stable JSONL event stream schema."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal, Optional, Union

from uniqdiff._typing import KeySpec
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
    yield from _duplicate_events(
        "right", result.duplicates_second, key=key, key_columns=columns
    )

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
    for row in rows:
        key_value = event_key(row.get("key"), key_columns=key_columns)
        changes = list(row.get("changes", ()))
        changed_columns = [str(change["field"]) for change in changes if "field" in change]
        if changed_columns:
            changed_rows += 1
            yield _event("row_changed", key=key_value, changed_columns=changed_columns)
        for change in changes:
            changed_fields += 1
            yield _event(
                "field_change",
                key=key_value,
                column=change["field"],
                left=change.get("left"),
                right=change.get("right"),
            )

    yield build_summary_event(
        left_rows=int(stats.get("first_count", 0)),
        right_rows=int(stats.get("second_count", 0)),
        common_rows=int(stats.get("compared_count", 0)),
        changed_rows=int(stats.get("changed_row_count", changed_rows)),
        changed_fields=int(stats.get("changed_field_count", changed_fields)),
    )


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
