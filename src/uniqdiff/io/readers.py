"""File readers used by compare_files."""

from __future__ import annotations

import csv
import gzip
import importlib
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Optional, TextIO, Union

from uniqdiff.exceptions import (
    CorruptedInputError,
    MissingOptionalDependencyError,
    UnsupportedFormatError,
)


def read_csv(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
) -> Iterator[Any]:
    """Yield CSV rows as dictionaries."""

    yield from read_delimited(
        path,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
    )


def read_tsv(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    delimiter: str = "\t",
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
) -> Iterator[Any]:
    """Yield TSV rows as dictionaries."""

    yield from read_delimited(
        path,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
    )


def read_delimited(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
) -> Iterator[Any]:
    """Yield delimited rows as dictionaries or lists.

    When `has_header` is false and `fieldnames` is omitted, rows are yielded as
    lists. When `fieldnames` is provided, rows are yielded as dictionaries.
    """

    with open_text(path, encoding=encoding, newline="") as file:
        if has_header or fieldnames is not None:
            dict_reader = csv.DictReader(
                file,
                fieldnames=None if has_header else fieldnames,
                delimiter=delimiter,
                quotechar=quotechar,
            )
            yield from dict_reader
            return

        list_reader = csv.reader(file, delimiter=delimiter, quotechar=quotechar)
        yield from list_reader


def read_jsonl(path: Union[str, Path], *, encoding: str = "utf-8") -> Iterator[Any]:
    """Yield JSON values from a JSON Lines file."""

    with open_text(path, encoding=encoding) as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise CorruptedInputError(
                    f"Invalid JSONL at line {line_number} in {path!s}: {exc.msg}"
                ) from exc


def read_parquet(
    path: Union[str, Path],
    *,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
) -> Iterator[dict[str, Any]]:
    """Yield Parquet rows as dictionaries using optional pyarrow."""

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    parquet = _load_pyarrow_parquet()
    parquet_file = parquet.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        yield from batch.to_pylist()


def read_text(path: Union[str, Path], *, encoding: str = "utf-8") -> Iterator[str]:
    """Yield stripped text lines."""

    with open_text(path, encoding=encoding) as file:
        for line in file:
            yield line.rstrip("\n")


def infer_format(path: Union[str, Path]) -> str:
    """Infer input format from file extension."""

    suffixes = [suffix.lower() for suffix in Path(path).suffixes]
    if suffixes and suffixes[-1] == ".gz":
        suffixes = suffixes[:-1]
    suffix = suffixes[-1] if suffixes else ""
    if suffix == ".csv":
        return "csv"
    if suffix in {".tsv", ".tab"}:
        return "tsv"
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl"
    if suffix == ".parquet":
        return "parquet"
    if suffix in {".txt", ".log"}:
        return "txt"
    raise UnsupportedFormatError(f"Cannot infer format for {path!s}")


def read_file(
    path: Union[str, Path],
    *,
    format: str = "auto",
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
) -> Iterator[Any]:
    """Yield rows/items from a supported file format."""

    selected = _normalize_format(infer_format(path) if format == "auto" else format)
    if selected == "csv":
        return read_csv(
            path,
            encoding=encoding,
            delimiter="," if delimiter is None else delimiter,
            quotechar=quotechar,
            has_header=has_header,
            fieldnames=fieldnames,
        )
    if selected == "tsv":
        return read_tsv(
            path,
            encoding=encoding,
            delimiter="\t" if delimiter is None else delimiter,
            quotechar=quotechar,
            has_header=has_header,
            fieldnames=fieldnames,
        )
    if selected == "jsonl":
        return read_jsonl(path, encoding=encoding)
    if selected == "parquet":
        return read_parquet(path, columns=columns, batch_size=batch_size)
    if selected in {"txt", "text"}:
        return read_text(path, encoding=encoding)
    raise UnsupportedFormatError(f"Unsupported format: {format}")


@contextmanager
def open_text(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    newline: Union[str, None] = None,
) -> Iterator[TextIO]:
    """Open plain text or gzip-compressed text files."""

    selected_path = Path(path)
    if selected_path.suffix.lower() == ".gz":
        with (
            gzip.open(selected_path, "rb") as binary_file,
            TextIOWrapper(binary_file, encoding=encoding, newline=newline) as text_file,
        ):
            yield text_file
        return

    with selected_path.open("r", encoding=encoding, newline=newline) as file:
        yield file


def _normalize_format(format: str) -> str:
    normalized = format.lower().strip().replace("-", "_")
    aliases = {
        "text": "txt",
        "tab": "tsv",
    }
    return aliases.get(normalized, normalized)


def _load_pyarrow_parquet() -> Any:
    try:
        return importlib.import_module("pyarrow.parquet")
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "Parquet support requires pyarrow. Install it with: pip install 'uniqdiff[parquet]'"
        ) from exc
