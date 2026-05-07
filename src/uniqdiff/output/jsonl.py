"""JSONL event stream writer."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Optional, TextIO, Union

from uniqdiff._utils import parse_size

_ENVELOPE_EVENT_TYPES = {"metadata", "summary"}


class JsonlWriter:
    """Write compact JSONL events with optional bounded buffering and limits.

    `max_output_rows` limits data events, excluding the metadata/summary envelope.
    `max_output_bytes` limits data-event bytes; metadata and summary are still
    written so the JSONL stream remains parseable and machine-friendly.
    """

    def __init__(
        self,
        fp: TextIO,
        *,
        flush: bool = False,
        buffer_size: int = 1,
        max_output_rows: Optional[int] = None,
        max_output_bytes: Optional[Union[str, int]] = None,
    ) -> None:
        if buffer_size < 1:
            raise ValueError("buffer_size must be greater than zero")
        if max_output_rows is not None and max_output_rows < 0:
            raise ValueError("max_output_rows must be greater than or equal to zero")
        self.fp = fp
        self.flush = flush
        self.buffer_size = buffer_size
        self.max_output_rows = max_output_rows
        self.max_output_bytes = (
            parse_size(max_output_bytes) if max_output_bytes is not None else None
        )
        self.emitted_data_events = 0
        self.skipped_events = 0
        self.bytes_written = 0
        self.data_bytes_written = 0
        self.truncated = False
        self._buffer: list[str] = []

    def write_event(self, event: Mapping[str, Any]) -> bool:
        """Write one JSONL event.

        The writer does not buffer a collection of events. Each call writes exactly one
        independently parseable JSON object followed by a newline.
        """

        event_type = event.get("type")
        envelope = event_type in _ENVELOPE_EVENT_TYPES
        if not envelope and self._over_row_limit():
            self._mark_skipped()
            return False

        output_event = self._summary_event(event) if event_type == "summary" else event
        line = _event_line(output_event)

        if not envelope and self._over_byte_limit(len(line.encode("utf-8"))):
            self._mark_skipped()
            return False

        line_size = len(line.encode("utf-8"))
        self._write_line(line, size=line_size)
        if not envelope:
            self.emitted_data_events += 1
            self.data_bytes_written += line_size
        return True

    def flush_buffer(self) -> None:
        """Flush pending buffered lines."""

        if not self._buffer:
            return
        self.fp.write("".join(self._buffer))
        self._buffer.clear()
        if self.flush:
            self.fp.flush()

    def _write_line(self, line: str, *, size: int) -> None:
        self._buffer.append(line)
        self.bytes_written += size
        if len(self._buffer) >= self.buffer_size or self.flush:
            self.flush_buffer()

    def _over_row_limit(self) -> bool:
        return (
            self.max_output_rows is not None
            and self.emitted_data_events >= self.max_output_rows
        )

    def _over_byte_limit(self, next_size: int) -> bool:
        return (
            self.max_output_bytes is not None
            and self.data_bytes_written + next_size > self.max_output_bytes
        )

    def _mark_skipped(self) -> None:
        self.skipped_events += 1
        self.truncated = True

    def _summary_event(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        if (
            not self.truncated
            and self.max_output_rows is None
            and self.max_output_bytes is None
        ):
            return event
        summary = dict(event)
        summary.setdefault("output_truncated", self.truncated)
        summary.setdefault("emitted_events", self.emitted_data_events)
        summary.setdefault("skipped_events", self.skipped_events)
        summary.setdefault("output_bytes", self.bytes_written)
        return summary

    def close(self) -> None:
        """Flush the buffer. Does not close the underlying file object."""

        self.flush_buffer()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def write_jsonl_events(
    fp: TextIO,
    events: Iterable[Mapping[str, Any]],
    *,
    flush: bool = False,
    buffer_size: int = 64,
    max_output_rows: Optional[int] = None,
    max_output_bytes: Optional[Union[str, int]] = None,
) -> int:
    """Write events to a file-like object and return the number of events written."""

    writer = JsonlWriter(
        fp,
        flush=flush,
        buffer_size=buffer_size,
        max_output_rows=max_output_rows,
        max_output_bytes=max_output_bytes,
    )
    count = 0
    try:
        for event in events:
            if writer.write_event(event):
                count += 1
    finally:
        writer.close()
    return count


def _event_line(event: Mapping[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, default=str, separators=(",", ":")) + "\n"
