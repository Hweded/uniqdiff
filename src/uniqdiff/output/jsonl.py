"""JSONL event stream writer."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, TextIO


class JsonlWriter:
    """Write one compact JSON object per line."""

    def __init__(self, fp: TextIO, *, flush: bool = False) -> None:
        self.fp = fp
        self.flush = flush

    def write_event(self, event: Mapping[str, Any]) -> None:
        """Write one JSONL event.

        The writer does not buffer a collection of events. Each call writes exactly one
        independently parseable JSON object followed by a newline.
        """

        self.fp.write(json.dumps(event, ensure_ascii=False, default=str, separators=(",", ":")))
        self.fp.write("\n")
        if self.flush:
            self.fp.flush()


def write_jsonl_events(
    fp: TextIO,
    events: Iterable[Mapping[str, Any]],
    *,
    flush: bool = False,
) -> int:
    """Write events to a file-like object and return the number of events written."""

    writer = JsonlWriter(fp, flush=flush)
    count = 0
    for event in events:
        writer.write_event(event)
        count += 1
    return count
