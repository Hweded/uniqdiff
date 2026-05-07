"""Field-level comparison helpers for structured rows."""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff._typing import KeySpec, Normalizer
from uniqdiff._utils import parse_size
from uniqdiff.exceptions import InvalidInputError, KeyExtractionError
from uniqdiff.io.readers import read_file
from uniqdiff.output import _json_dumps
from uniqdiff.tokens import extract_key

_NO_OUTPUT_WARNING = "Field diff rows were streamed to output and are not materialized."
_TRUNCATED_WARNING = "Field diff output was truncated by max_rows or max_bytes."
_SORTED_COUNTS_WARNING = (
    "Sorted field diff streams changed rows and does not materialize full input row counts."
)
_DUPLICATE_RIGHT_KEY_WARNING = (
    "Duplicate keys were found in the second input; only the first row per key was used."
)


@dataclass(frozen=True)
class FieldChange:
    """One changed field inside a keyed row."""

    field: str
    left: Any
    right: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "left": self.left, "right": self.right}


@dataclass(frozen=True)
class FieldDiffStats:
    """Statistics for field-level comparison."""

    first_count: int = 0
    second_count: int = 0
    compared_count: int = 0
    changed_row_count: int = 0
    changed_field_count: int = 0
    emitted_row_count: int = 0
    output_bytes: int = 0
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_count": self.first_count,
            "second_count": self.second_count,
            "compared_count": self.compared_count,
            "changed_row_count": self.changed_row_count,
            "changed_field_count": self.changed_field_count,
            "emitted_row_count": self.emitted_row_count,
            "output_bytes": self.output_bytes,
            "truncated": self.truncated,
        }


@dataclass
class FieldDiffResult:
    """Result of field-level comparison.

    When `output` is used, changed rows are streamed to JSONL and `rows` stays
    empty. Summary and stats are still returned in memory.
    """

    rows: list[dict[str, Any]] = field(default_factory=list)
    summary_by_column: dict[str, int] = field(default_factory=dict)
    stats: FieldDiffStats = field(default_factory=FieldDiffStats)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "summary_by_column": self.summary_by_column,
            "stats": self.stats.to_dict(),
            "metadata": self.metadata,
            "warnings": self.warnings,
        }


def compare_fields(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: KeySpec,
    columns: Optional[Sequence[str]] = None,
    exclude_columns: Optional[Sequence[str]] = None,
    normalizer: Optional[Normalizer] = None,
    output: Optional[Union[str, os.PathLike[str]]] = None,
    max_rows: Optional[int] = None,
    max_bytes: Optional[Union[str, int]] = None,
) -> FieldDiffResult:
    """Compare changed fields for rows that share the same comparison key.

    The current engine implementation indexes the second input by key and then
    streams the first input. Large result sets should use `output` to avoid
    materializing changed rows in memory.
    """

    config = _build_config(
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        normalizer=normalizer,
        max_rows=max_rows,
        max_bytes=max_bytes,
    )
    right_index = _index_rows_by_key(second, key_extractor=config.key_extractor)
    accumulator = _FieldDiffAccumulator()

    with _JSONLFieldWriter.open_optional(output, max_bytes=config.max_bytes) as writer:
        for left_row in first:
            accumulator.first_count += 1
            token = config.key_extractor(left_row)
            right_row = right_index.rows.get(token)
            if right_row is None:
                continue

            accumulator.compared_count += 1
            changed = _changed_fields(
                left_row,
                right_row,
                config=config,
            )
            if not changed:
                continue

            accumulator.record_changed(changed)
            if not accumulator.can_emit(config.max_rows):
                accumulator.truncated = True
                continue

            output_row = {
                "key": token,
                "changes": [change.to_dict() for change in changed],
            }
            if writer is not None:
                if not writer.write(output_row):
                    accumulator.truncated = True
                    continue
                accumulator.output_bytes = writer.bytes_written
            else:
                accumulator.rows.append(output_row)
            accumulator.emitted_row_count += 1

    return _build_result(
        accumulator,
        right_index=right_index,
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        output=output,
    )


def iter_field_diff_sorted(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: KeySpec,
    columns: Optional[Sequence[str]] = None,
    exclude_columns: Optional[Sequence[str]] = None,
    normalizer: Optional[Normalizer] = None,
    validate_sorted: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield field-diff rows for inputs sorted by comparison key.

    This streaming helper keeps only the current equal-key group from each input in
    memory. It is intended for large inputs that can be pre-sorted by the same key
    and normalization rules.
    """

    config = _build_config(
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        normalizer=normalizer,
        max_rows=None,
        max_bytes=None,
    )
    left_groups = _iter_key_groups(
        first,
        key_extractor=config.key_extractor,
        validate_sorted=validate_sorted,
    )
    right_groups = _iter_key_groups(
        second,
        key_extractor=config.key_extractor,
        validate_sorted=validate_sorted,
    )
    left_item = next(left_groups, None)
    right_item = next(right_groups, None)

    while left_item is not None and right_item is not None:
        left_key, left_rows = left_item
        right_key, right_rows = right_item
        if left_key < right_key:
            left_item = next(left_groups, None)
            continue
        if right_key < left_key:
            right_item = next(right_groups, None)
            continue

        changed = _changed_fields(left_rows[0], right_rows[0], config=config)
        if changed:
            yield {
                "key": left_key,
                "changes": [change.to_dict() for change in changed],
            }
        left_item = next(left_groups, None)
        right_item = next(right_groups, None)


def compare_fields_sorted(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: KeySpec,
    columns: Optional[Sequence[str]] = None,
    exclude_columns: Optional[Sequence[str]] = None,
    normalizer: Optional[Normalizer] = None,
    output: Optional[Union[str, os.PathLike[str]]] = None,
    max_rows: Optional[int] = None,
    max_bytes: Optional[Union[str, int]] = None,
    validate_sorted: bool = True,
) -> FieldDiffResult:
    """Compare changed fields for inputs already sorted by key.

    This result-oriented helper is the bounded-memory counterpart to
    `compare_fields()`. It streams both inputs and keeps only the current equal-key
    groups in memory. Full input row counts are intentionally not materialized.
    """

    rows = iter_field_diff_sorted(
        first,
        second,
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        normalizer=normalizer,
        validate_sorted=validate_sorted,
    )
    return _build_sorted_result(
        rows,
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        output=output,
        max_rows=max_rows,
        max_bytes=max_bytes,
    )


def iter_field_diff_rows(output: Union[str, os.PathLike[str]]) -> Iterator[dict[str, Any]]:
    """Yield field-diff rows lazily from a JSONL field diff output file."""

    output_path = Path(output)
    if output_path.suffix.lower() != ".jsonl":
        raise InvalidInputError("field diff lazy reading supports only .jsonl output")
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise InvalidInputError("field diff JSONL row must be an object")
            yield row


def compare_fields_files(
    file_a: str,
    file_b: str,
    *,
    key: KeySpec,
    format: str = "auto",
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
    **kwargs: Any,
) -> FieldDiffResult:
    """Compare changed fields for two supported files."""

    read_columns = _read_columns(columns, key)
    first = read_file(
        file_a,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=batch_size,
    )
    second = read_file(
        file_b,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=batch_size,
    )
    return compare_fields(first, second, key=key, columns=columns, **kwargs)


def compare_fields_files_sorted(
    file_a: str,
    file_b: str,
    *,
    key: KeySpec,
    format: str = "auto",
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
    **kwargs: Any,
) -> FieldDiffResult:
    """Read supported files and run sorted streaming field comparison."""

    read_columns = _read_columns(columns, key)
    first = read_file(
        file_a,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=batch_size,
    )
    second = read_file(
        file_b,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=batch_size,
    )
    return compare_fields_sorted(first, second, key=key, columns=columns, **kwargs)


def _changed_fields(
    left_row: Any,
    right_row: Any,
    *,
    config: _FieldDiffConfig,
) -> list[FieldChange]:
    left = _as_mapping(left_row)
    right = _as_mapping(right_row)
    field_names: Sequence[str]
    if config.field_names is not None:
        field_names = config.field_names
    else:
        field_names = _field_names(
            left,
            right,
            columns=config.columns,
            exclude_columns=config.dynamic_exclude_columns,
        )
    changes: list[FieldChange] = []
    if config.normalizer is None:
        for field_name in field_names:
            left_value = left.get(field_name)
            right_value = right.get(field_name)
            if left_value != right_value:
                changes.append(FieldChange(field=field_name, left=left_value, right=right_value))
        return changes

    normalizer = config.normalizer
    for field_name in field_names:
        left_value = left.get(field_name)
        right_value = right.get(field_name)
        if normalizer(left_value) != normalizer(right_value):
            changes.append(FieldChange(field=field_name, left=left_value, right=right_value))
    return changes


@dataclass(frozen=True)
class _FieldDiffConfig:
    key_extractor: Callable[[Any], Any]
    columns: Optional[set[str]]
    exclude_columns: set[str]
    dynamic_exclude_columns: set[str]
    field_names: Optional[tuple[str, ...]]
    key_columns: set[str]
    normalizer: Optional[Normalizer]
    max_rows: Optional[int]
    max_bytes: Optional[int]


@dataclass
class _FieldDiffAccumulator:
    rows: list[dict[str, Any]] = field(default_factory=list)
    summary: Counter[str] = field(default_factory=Counter)
    first_count: int = 0
    compared_count: int = 0
    changed_row_count: int = 0
    changed_field_count: int = 0
    emitted_row_count: int = 0
    output_bytes: int = 0
    truncated: bool = False

    def record_changed(self, changes: Sequence[FieldChange]) -> None:
        self.changed_row_count += 1
        self.changed_field_count += len(changes)
        for change in changes:
            self.summary[change.field] += 1

    def can_emit(self, max_rows: Optional[int]) -> bool:
        return max_rows is None or self.emitted_row_count < max_rows


@dataclass(frozen=True)
class _KeyIndex:
    rows: dict[Any, Any]
    count: int
    duplicate_key_count: int


def _build_config(
    *,
    key: KeySpec,
    columns: Optional[Sequence[str]],
    exclude_columns: Optional[Sequence[str]],
    normalizer: Optional[Normalizer],
    max_rows: Optional[int],
    max_bytes: Optional[Union[str, int]],
) -> _FieldDiffConfig:
    if key is None:
        raise InvalidInputError("compare_fields requires key")
    if max_rows is not None and max_rows < 0:
        raise InvalidInputError("max_rows must be greater than or equal to zero")
    column_set = _column_set(columns)
    exclude_set = _column_set(exclude_columns) or set()
    key_columns = _key_columns(key)
    return _FieldDiffConfig(
        key_extractor=_make_key_extractor(key),
        columns=column_set,
        exclude_columns=exclude_set,
        dynamic_exclude_columns=exclude_set | (key_columns if column_set is None else set()),
        field_names=_static_field_names(column_set, exclude_set),
        key_columns=key_columns,
        normalizer=normalizer,
        max_rows=max_rows,
        max_bytes=parse_size(max_bytes) if max_bytes is not None else None,
    )


def _index_rows_by_key(
    rows: Iterable[Any],
    *,
    key_extractor: Callable[[Any], Any],
) -> _KeyIndex:
    indexed: dict[Any, Any] = {}
    count = 0
    duplicate_key_count = 0
    for row in rows:
        token = key_extractor(row)
        if token in indexed:
            duplicate_key_count += 1
        else:
            indexed[token] = row
        count += 1
    return _KeyIndex(rows=indexed, count=count, duplicate_key_count=duplicate_key_count)


def _build_result(
    accumulator: _FieldDiffAccumulator,
    *,
    right_index: _KeyIndex,
    key: KeySpec,
    columns: Optional[Sequence[str]],
    exclude_columns: Optional[Sequence[str]],
    output: Optional[Union[str, os.PathLike[str]]],
) -> FieldDiffResult:
    stats = FieldDiffStats(
        first_count=accumulator.first_count,
        second_count=right_index.count,
        compared_count=accumulator.compared_count,
        changed_row_count=accumulator.changed_row_count,
        changed_field_count=accumulator.changed_field_count,
        emitted_row_count=accumulator.emitted_row_count,
        output_bytes=accumulator.output_bytes,
        truncated=accumulator.truncated,
    )
    warnings = _result_warnings(
        output=output,
        truncated=accumulator.truncated,
        duplicate_right_key_count=right_index.duplicate_key_count,
    )
    return FieldDiffResult(
        rows=accumulator.rows,
        summary_by_column=dict(accumulator.summary),
        stats=stats,
        metadata={
            "key": _metadata_key(key),
            "columns": list(columns) if columns is not None else None,
            "exclude_columns": list(exclude_columns) if exclude_columns is not None else None,
            "output": str(output) if output is not None else None,
            "result_mode": "file" if output is not None else "memory",
            "duplicate_second_key_count": right_index.duplicate_key_count,
        },
        warnings=warnings,
    )


def _build_sorted_result(
    rows: Iterable[dict[str, Any]],
    *,
    key: KeySpec,
    columns: Optional[Sequence[str]],
    exclude_columns: Optional[Sequence[str]],
    output: Optional[Union[str, os.PathLike[str]]],
    max_rows: Optional[int],
    max_bytes: Optional[Union[str, int]],
) -> FieldDiffResult:
    config = _build_config(
        key=key,
        columns=columns,
        exclude_columns=exclude_columns,
        normalizer=None,
        max_rows=max_rows,
        max_bytes=max_bytes,
    )
    accumulator = _FieldDiffAccumulator()

    with _JSONLFieldWriter.open_optional(output, max_bytes=config.max_bytes) as writer:
        for row in rows:
            changes = list(row.get("changes", ()))
            accumulator.changed_row_count += 1
            accumulator.changed_field_count += len(changes)
            for change in changes:
                accumulator.summary[str(change.get("field"))] += 1

            if not accumulator.can_emit(config.max_rows):
                accumulator.truncated = True
                continue
            if writer is not None:
                if not writer.write(row):
                    accumulator.truncated = True
                    continue
                accumulator.output_bytes = writer.bytes_written
            else:
                accumulator.rows.append(row)
            accumulator.emitted_row_count += 1

    return FieldDiffResult(
        rows=accumulator.rows,
        summary_by_column=dict(accumulator.summary),
        stats=FieldDiffStats(
            changed_row_count=accumulator.changed_row_count,
            changed_field_count=accumulator.changed_field_count,
            emitted_row_count=accumulator.emitted_row_count,
            output_bytes=accumulator.output_bytes,
            truncated=accumulator.truncated,
        ),
        metadata={
            "key": _metadata_key(key),
            "columns": list(columns) if columns is not None else None,
            "exclude_columns": list(exclude_columns) if exclude_columns is not None else None,
            "output": str(output) if output is not None else None,
            "result_mode": "file" if output is not None else "memory",
            "sorted_input": True,
        },
        warnings=_sorted_result_warnings(output=output, truncated=accumulator.truncated),
    )


def _result_warnings(
    *,
    output: Optional[Union[str, os.PathLike[str]]],
    truncated: bool,
    duplicate_right_key_count: int,
) -> list[str]:
    warnings = []
    if output is not None:
        warnings.append(_NO_OUTPUT_WARNING)
    if truncated:
        warnings.append(_TRUNCATED_WARNING)
    if duplicate_right_key_count:
        warnings.append(_DUPLICATE_RIGHT_KEY_WARNING)
    return warnings


def _sorted_result_warnings(
    *,
    output: Optional[Union[str, os.PathLike[str]]],
    truncated: bool,
) -> list[str]:
    warnings = [_SORTED_COUNTS_WARNING]
    if output is not None:
        warnings.append(_NO_OUTPUT_WARNING)
    if truncated:
        warnings.append(_TRUNCATED_WARNING)
    return warnings


def _as_mapping(row: Any) -> Mapping[str, Any]:
    if type(row) is dict:
        return row
    if isinstance(row, Mapping):
        return row
    if is_dataclass(row) and not isinstance(row, type):
        return asdict(row)
    values = getattr(row, "__dict__", None)
    if isinstance(values, Mapping):
        return values
    raise InvalidInputError("field comparison requires dict-like, dataclass, or object rows")


def _field_names(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    columns: Optional[set[str]],
    exclude_columns: set[str],
) -> list[str]:
    candidates = columns if columns is not None else set(left) | set(right)
    return sorted(field for field in candidates if field not in exclude_columns)


def _static_field_names(
    columns: Optional[set[str]],
    exclude_columns: set[str],
) -> Optional[tuple[str, ...]]:
    if columns is None:
        return None
    return tuple(sorted(field for field in columns if field not in exclude_columns))


def _column_set(columns: Optional[Sequence[str]]) -> Optional[set[str]]:
    if columns is None:
        return None
    return {column for column in columns if column}


def _key_columns(key: KeySpec) -> set[str]:
    if isinstance(key, str):
        return {key}
    if isinstance(key, (tuple, list)):
        return {part for part in key if isinstance(part, str)}
    return set()


def _read_columns(columns: Optional[Sequence[str]], key: KeySpec) -> Optional[tuple[str, ...]]:
    if columns is None:
        return None
    selected = list(dict.fromkeys([*columns, *_key_columns(key)]))
    return tuple(selected)


def _metadata_key(key: KeySpec) -> Any:
    if isinstance(key, list):
        return tuple(key)
    if callable(key):
        return getattr(key, "__name__", repr(key))
    return key


def _make_key_extractor(key: KeySpec) -> Callable[[Any], Any]:
    if isinstance(key, str):

        def extract_str(row: Any) -> Any:
            if type(row) is dict:
                try:
                    return row[key]
                except KeyError as exc:
                    raise KeyExtractionError(f"Missing key {key!r} in item {row!r}") from exc
            return extract_key(row, key)

        return extract_str

    if isinstance(key, (tuple, list)) and all(isinstance(part, str) for part in key):
        parts = tuple(key)

        def extract_parts(row: Any) -> tuple[Any, ...]:
            if type(row) is dict:
                try:
                    return tuple(row[part] for part in parts)
                except KeyError as exc:
                    missing = exc.args[0]
                    raise KeyExtractionError(
                        f"Missing key {missing!r} in item {row!r}"
                    ) from exc
            return tuple(extract_key(row, part) for part in parts)

        return extract_parts

    return lambda row: extract_key(row, key)


def _iter_key_groups(
    rows: Iterable[Any],
    *,
    key_extractor: Callable[[Any], Any],
    validate_sorted: bool,
) -> Iterator[tuple[Any, list[Any]]]:
    previous_token: Any = None
    current_token: Any = None
    current_rows: list[Any] = []
    has_previous = False

    for row in rows:
        token = key_extractor(row)
        if validate_sorted and has_previous and token < previous_token:
            raise InvalidInputError("sorted field diff input is not sorted by key")
        previous_token = token
        has_previous = True
        if current_token is None:
            current_token = token
        if token != current_token:
            yield current_token, current_rows
            current_token = token
            current_rows = []
        current_rows.append(row)

    if current_token is not None:
        yield current_token, current_rows


class _JSONLFieldWriter:
    def __init__(
        self,
        output: Union[str, os.PathLike[str]],
        *,
        max_bytes: Optional[int],
    ) -> None:
        self.output_path = Path(output)
        if self.output_path.suffix.lower() != ".jsonl":
            raise InvalidInputError("field diff streaming output supports only .jsonl")
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self._temp_path: Optional[Path] = None
        self._file: Any = None
        self._closed = False
        self._failed = False

    @classmethod
    def open_optional(
        cls,
        output: Optional[Union[str, os.PathLike[str]]],
        *,
        max_bytes: Optional[int],
    ) -> _OptionalJSONLFieldWriter:
        return _OptionalJSONLFieldWriter(output, max_bytes=max_bytes)

    def open(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.output_path.name}.",
            dir=str(self.output_path.parent),
        )
        os.close(fd)
        self._temp_path = Path(temp_name)
        self._file = self._temp_path.open("w", encoding="utf-8", newline="")

    def write(self, row: dict[str, Any]) -> bool:
        line = _field_diff_jsonl_line(row)
        encoded_size = len(line.encode("utf-8"))
        if self.max_bytes is not None and self.bytes_written + encoded_size > self.max_bytes:
            return False
        self._file.write(line)
        self.bytes_written += encoded_size
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._file is not None:
            self._file.close()
        if self._temp_path is None:
            return
        if self._failed:
            self._temp_path.unlink(missing_ok=True)
            return
        os.replace(self._temp_path, self.output_path)

    def abort(self) -> None:
        self._failed = True


class _OptionalJSONLFieldWriter:
    def __init__(
        self,
        output: Optional[Union[str, os.PathLike[str]]],
        *,
        max_bytes: Optional[int],
    ) -> None:
        self.output = output
        self.max_bytes = max_bytes
        self.writer: Optional[_JSONLFieldWriter] = None

    def __enter__(self) -> Optional[_JSONLFieldWriter]:
        if self.output is None:
            return None
        self.writer = _JSONLFieldWriter(self.output, max_bytes=self.max_bytes)
        self.writer.open()
        return self.writer

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.writer is None:
            return
        if exc_type is not None:
            self.writer.abort()
        self.writer.close()


def _field_diff_jsonl_line(row: dict[str, Any]) -> str:
    return (
        '{"key":'
        + _json_dumps(row["key"])
        + ',"changes":'
        + json.dumps(row["changes"], ensure_ascii=False, default=str, separators=(",", ":"))
        + "}\n"
    )
