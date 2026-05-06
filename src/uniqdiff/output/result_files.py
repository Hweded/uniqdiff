"""Legacy section/value result output helpers."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Callable, Iterable, Iterator
from json.encoder import encode_basestring
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff.exceptions import UnsupportedFormatError


class StreamingResultWriter:
    """Atomically stream comparison rows to JSONL or CSV."""

    def __init__(self, output: Union[str, os.PathLike[str]]) -> None:
        self.output_path = Path(output)
        self.suffix = self.output_path.suffix.lower()
        if self.suffix not in {".jsonl", ".csv"}:
            raise UnsupportedFormatError(
                "Streaming result_mode='file' supports only .jsonl and .csv output"
            )
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._temp_path: Optional[Path] = None
        self._file: Any = None
        self._csv_writer: Optional[csv.DictWriter[str]] = None
        self._json_dumps: Callable[[Any], str] = _json_dumps

    def __enter__(self) -> StreamingResultWriter:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.output_path.name}.",
            dir=str(self.output_path.parent),
        )
        os.close(fd)
        self._temp_path = Path(temp_name)
        self._file = self._temp_path.open("w", encoding="utf-8", newline="")
        if self.suffix == ".csv":
            self._csv_writer = csv.DictWriter(self._file, fieldnames=["section", "value"])
            self._csv_writer.writeheader()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._file is not None:
            self._file.close()
        if self._temp_path is None:
            return
        if exc_type is None:
            os.replace(self._temp_path, self.output_path)
        else:
            self._temp_path.unlink(missing_ok=True)

    def write(self, section: str, value: Any) -> None:
        """Write one result row."""

        if self.suffix == ".jsonl":
            self._file.write('{"section":')
            self._file.write(encode_basestring(section))
            self._file.write(',"value":')
            self._file.write(self._json_dumps(value))
            self._file.write("}\n")
            return

        if self._csv_writer is None:
            raise RuntimeError("CSV writer is not initialized")
        self._csv_writer.writerow(
            {"section": section, "value": self._json_dumps(value)}
        )


def _json_dumps(value: Any) -> str:
    value_type = type(value)
    if value is None:
        return "null"
    if value_type is bool:
        return "true" if value else "false"
    if value_type is int:
        return str(value)
    if value_type is str:
        return encode_basestring(value)
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def ensure_result_mode(result_mode: str) -> str:
    """Validate result materialization mode."""

    normalized = result_mode.lower()
    if normalized not in {"memory", "file"}:
        raise ValueError("result_mode must be one of: 'memory', 'file'")
    return normalized


def iter_result_rows(
    output: Union[str, os.PathLike[str]],
    *,
    sections: Optional[Iterable[str]] = None,
) -> Iterator[dict[str, Any]]:
    """Yield result rows lazily from a JSONL or CSV result file."""

    output_path = Path(output)
    selected_sections = set(sections) if sections is not None else None
    if output_path.suffix.lower() == ".jsonl":
        yield from _iter_jsonl_result_rows(output_path, sections=selected_sections)
        return
    if output_path.suffix.lower() == ".csv":
        yield from _iter_csv_result_rows(output_path, sections=selected_sections)
        return
    raise UnsupportedFormatError("Lazy result reading supports only .jsonl and .csv output")


def iter_result_values(
    output: Union[str, os.PathLike[str]],
    *,
    sections: Optional[Iterable[str]] = None,
) -> Iterator[Any]:
    """Yield only row values lazily from a result file."""

    for row in iter_result_rows(output, sections=sections):
        yield row["value"]


def _iter_jsonl_result_rows(
    output_path: Path,
    *,
    sections: Optional[set[str]],
) -> Iterator[dict[str, Any]]:
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if sections is None or row.get("section") in sections:
                yield row


def _iter_csv_result_rows(
    output_path: Path,
    *,
    sections: Optional[set[str]],
) -> Iterator[dict[str, Any]]:
    with output_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            section = row.get("section")
            if sections is not None and section not in sections:
                continue
            yield {"section": section, "value": json.loads(row["value"])}
