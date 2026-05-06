"""External sorting disk backend."""

from __future__ import annotations

import heapq
import os
import tempfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff._utils import parse_size
from uniqdiff.exceptions import DiskLimitExceededError, TempStorageError
from uniqdiff.output import StreamingResultWriter
from uniqdiff.result import CompareResult, CompareStats
from uniqdiff.storage.codec import from_blob as _from_blob
from uniqdiff.storage.codec import read_record, write_record
from uniqdiff.storage.codec import to_blob as _to_blob

TokenFactory = Callable[[Any], Any]
SortRecord = tuple[bytes, int, bytes]
GroupedRecord = tuple[bytes, list[tuple[int, bytes]]]


def compare_external_sort(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    token_factory: TokenFactory,
    include_common: bool,
    include_duplicates: bool,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
    output: Optional[str] = None,
    result_mode: str = "memory",
) -> CompareResult:
    """Compare two iterables by sorting chunks on disk and merging token streams."""

    left_chunks: list[Path] = []
    right_chunks: list[Path] = []
    try:
        left_chunks, first_count = _write_sorted_chunks(
            first,
            side="first",
            token_factory=token_factory,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
            all_chunks=lambda: [*left_chunks, *right_chunks],
        )
        right_chunks, second_count = _write_sorted_chunks(
            second,
            side="second",
            token_factory=token_factory,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
            all_chunks=lambda: [*left_chunks, *right_chunks],
        )

        left_groups = _group_sorted_records(_merge_chunks(left_chunks))
        right_groups = _group_sorted_records(_merge_chunks(right_chunks))

        if result_mode == "file":
            if output is None:
                raise TempStorageError("result_mode='file' requires output")
            return _merge_grouped_to_file(
                left_groups,
                right_groups,
                output=output,
                include_common=include_common,
                include_duplicates=include_duplicates,
                first_count=first_count,
                second_count=second_count,
                mode=mode,
                strategy=strategy,
                metadata=metadata,
                left_chunk_count=len(left_chunks),
                right_chunk_count=len(right_chunks),
            )

        merge_result = _merge_grouped(
            left_groups,
            right_groups,
            include_common=include_common,
            include_duplicates=include_duplicates,
        )

        stats = CompareStats(
            first_count=first_count,
            second_count=second_count,
            unique_first_count=merge_result.unique_first_count,
            unique_second_count=merge_result.unique_second_count,
            only_in_first_count=len(merge_result.only_in_first),
            only_in_second_count=len(merge_result.only_in_second),
            common_count=merge_result.common_count,
            duplicate_first_count=0
            if merge_result.duplicates_first is None
            else len(merge_result.duplicates_first),
            duplicate_second_count=0
            if merge_result.duplicates_second is None
            else len(merge_result.duplicates_second),
            mode=mode,
            strategy=strategy,
        )

        return CompareResult(
            only_in_first=[] if result_mode == "file" else merge_result.only_in_first,
            only_in_second=[] if result_mode == "file" else merge_result.only_in_second,
            common=None if result_mode == "file" else merge_result.common,
            unique=[]
            if result_mode == "file"
            else [*merge_result.only_in_first, *merge_result.only_in_second],
            duplicates_first=None if result_mode == "file" else merge_result.duplicates_first,
            duplicates_second=None if result_mode == "file" else merge_result.duplicates_second,
            stats=stats,
            metadata={
                **metadata,
                "backend": "external_sort",
                "output": output,
                "result_mode": result_mode,
                "sorted_chunks_removed": True,
                "left_chunk_count": len(left_chunks),
                "right_chunk_count": len(right_chunks),
            },
            warnings=_file_mode_warnings(result_mode),
        )
    finally:
        for path in [*left_chunks, *right_chunks]:
            path.unlink(missing_ok=True)


def duplicates_external_sort(
    data: Iterable[Any],
    *,
    token_factory: TokenFactory,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
) -> list[Any]:
    """Find duplicates using external sorting."""

    chunks: list[Path] = []
    try:
        chunks, _ = _write_sorted_chunks(
            data,
            side="duplicates",
            token_factory=token_factory,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
            all_chunks=lambda: chunks,
        )
        rows: list[tuple[int, Any]] = []
        for _, values in _group_sorted_records(_merge_chunks(chunks)):
            if len(values) > 1:
                rows.extend((ordinal, _from_blob(payload)) for ordinal, payload in values[1:])
        return _values_by_ordinal(rows)
    finally:
        for path in chunks:
            path.unlink(missing_ok=True)


class _MergeResult:
    def __init__(
        self,
        *,
        only_in_first: list[Any],
        only_in_second: list[Any],
        common: Optional[list[Any]],
        duplicates_first: Optional[list[Any]],
        duplicates_second: Optional[list[Any]],
        unique_first_count: int,
        unique_second_count: int,
        common_count: int,
    ) -> None:
        self.only_in_first = only_in_first
        self.only_in_second = only_in_second
        self.common = common
        self.duplicates_first = duplicates_first
        self.duplicates_second = duplicates_second
        self.unique_first_count = unique_first_count
        self.unique_second_count = unique_second_count
        self.common_count = common_count


def _merge_grouped(
    left: Iterator[GroupedRecord],
    right: Iterator[GroupedRecord],
    *,
    include_common: bool,
    include_duplicates: bool,
) -> _MergeResult:
    only_first_rows: list[tuple[int, Any]] = []
    only_second_rows: list[tuple[int, Any]] = []
    common_rows: list[tuple[int, Any]] = []
    duplicates_first_rows: list[tuple[int, Any]] = []
    duplicates_second_rows: list[tuple[int, Any]] = []
    unique_first_count = 0
    unique_second_count = 0
    common_count = 0

    left_item = next(left, None)
    right_item = next(right, None)
    while left_item is not None or right_item is not None:
        if right_item is None or (left_item is not None and left_item[0] < right_item[0]):
            if left_item is None:
                raise RuntimeError("External sort merge reached an invalid left state")
            _, rows = left_item
            unique_first_count += 1
            only_first_rows.append(_first_payload(rows))
            if include_duplicates:
                duplicates_first_rows.extend(_duplicate_payloads(rows))
            left_item = next(left, None)
            continue

        if left_item is None or right_item[0] < left_item[0]:
            _, rows = right_item
            unique_second_count += 1
            only_second_rows.append(_first_payload(rows))
            if include_duplicates:
                duplicates_second_rows.extend(_duplicate_payloads(rows))
            right_item = next(right, None)
            continue

        left_token, left_rows = left_item
        _, right_rows = right_item
        unique_first_count += 1
        unique_second_count += 1
        common_count += 1
        if include_common:
            common_rows.append(_first_payload(left_rows))
        if include_duplicates:
            duplicates_first_rows.extend(_duplicate_payloads(left_rows))
            duplicates_second_rows.extend(_duplicate_payloads(right_rows))
        left_item = next(left, None)
        right_item = next(right, None)

    return _MergeResult(
        only_in_first=_values_by_ordinal(only_first_rows),
        only_in_second=_values_by_ordinal(only_second_rows),
        common=_values_by_ordinal(common_rows) if include_common else None,
        duplicates_first=_values_by_ordinal(duplicates_first_rows) if include_duplicates else None,
        duplicates_second=(
            _values_by_ordinal(duplicates_second_rows) if include_duplicates else None
        ),
        unique_first_count=unique_first_count,
        unique_second_count=unique_second_count,
        common_count=common_count,
    )


def _merge_grouped_to_file(
    left: Iterator[GroupedRecord],
    right: Iterator[GroupedRecord],
    *,
    output: str,
    include_common: bool,
    include_duplicates: bool,
    first_count: int,
    second_count: int,
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
    left_chunk_count: int,
    right_chunk_count: int,
) -> CompareResult:
    unique_first_count = 0
    unique_second_count = 0
    only_in_first_count = 0
    only_in_second_count = 0
    common_count = 0
    duplicate_first_count = 0
    duplicate_second_count = 0

    with StreamingResultWriter(output) as writer:
        left_item = next(left, None)
        right_item = next(right, None)
        while left_item is not None or right_item is not None:
            if right_item is None or (left_item is not None and left_item[0] < right_item[0]):
                if left_item is None:
                    raise RuntimeError("External sort merge reached an invalid left state")
                _, rows = left_item
                unique_first_count += 1
                only_in_first_count += 1
                writer.write("only_in_first", _first_payload(rows)[1])
                if include_duplicates:
                    duplicates = _duplicate_payloads(rows)
                    duplicate_first_count += len(duplicates)
                    for _, value in duplicates:
                        writer.write("duplicates_first", value)
                left_item = next(left, None)
                continue

            if left_item is None or right_item[0] < left_item[0]:
                _, rows = right_item
                unique_second_count += 1
                only_in_second_count += 1
                writer.write("only_in_second", _first_payload(rows)[1])
                if include_duplicates:
                    duplicates = _duplicate_payloads(rows)
                    duplicate_second_count += len(duplicates)
                    for _, value in duplicates:
                        writer.write("duplicates_second", value)
                right_item = next(right, None)
                continue

            _, left_rows = left_item
            _, right_rows = right_item
            unique_first_count += 1
            unique_second_count += 1
            common_count += 1
            if include_common:
                writer.write("common", _first_payload(left_rows)[1])
            if include_duplicates:
                left_duplicates = _duplicate_payloads(left_rows)
                right_duplicates = _duplicate_payloads(right_rows)
                duplicate_first_count += len(left_duplicates)
                duplicate_second_count += len(right_duplicates)
                for _, value in left_duplicates:
                    writer.write("duplicates_first", value)
                for _, value in right_duplicates:
                    writer.write("duplicates_second", value)
            left_item = next(left, None)
            right_item = next(right, None)

    stats = CompareStats(
        first_count=first_count,
        second_count=second_count,
        unique_first_count=unique_first_count,
        unique_second_count=unique_second_count,
        only_in_first_count=only_in_first_count,
        only_in_second_count=only_in_second_count,
        common_count=common_count,
        duplicate_first_count=duplicate_first_count,
        duplicate_second_count=duplicate_second_count,
        mode=mode,
        strategy=strategy,
    )
    return CompareResult(
        only_in_first=[],
        only_in_second=[],
        common=None,
        unique=[],
        duplicates_first=None,
        duplicates_second=None,
        stats=stats,
        metadata={
            **metadata,
            "backend": "external_sort",
            "output": output,
            "result_mode": "file",
            "sorted_chunks_removed": True,
            "left_chunk_count": left_chunk_count,
            "right_chunk_count": right_chunk_count,
        },
        warnings=_file_mode_warnings("file"),
    )


def _write_sorted_chunks(
    items: Iterable[Any],
    *,
    side: str,
    token_factory: TokenFactory,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
    all_chunks: Callable[[], list[Path]],
) -> tuple[list[Path], int]:
    chunks: list[Path] = []
    batch: list[SortRecord] = []
    count = 0

    try:
        for item in items:
            batch.append((_to_blob(token_factory(item)), count, _to_blob(item)))
            count += 1
            if len(batch) >= chunk_size:
                chunks.append(_write_chunk(batch, side=side, temp_dir=temp_dir))
                _check_disk_limit(all_chunks(), disk_limit)
                batch.clear()

        if batch:
            chunks.append(_write_chunk(batch, side=side, temp_dir=temp_dir))
            _check_disk_limit(all_chunks(), disk_limit)
            batch.clear()

        if not chunks:
            chunks.append(_write_chunk([], side=side, temp_dir=temp_dir))
            _check_disk_limit(all_chunks(), disk_limit)
    except Exception:
        for path in chunks:
            path.unlink(missing_ok=True)
        raise

    return chunks, count


def _write_chunk(records: list[SortRecord], *, side: str, temp_dir: Optional[str]) -> Path:
    records.sort(key=lambda record: (record[0], record[1]))
    path = _make_temp_path(temp_dir, side)
    with path.open("wb") as file:
        for token, ordinal, payload in records:
            write_record(file, token, ordinal, payload)
    return path


def _merge_chunks(paths: list[Path]) -> Iterator[SortRecord]:
    iterators = [_read_chunk(path) for path in paths]
    yield from heapq.merge(*iterators, key=lambda record: (record[0], record[1]))


def _read_chunk(path: Path) -> Iterator[SortRecord]:
    with path.open("rb") as file:
        while True:
            record = read_record(file)
            if record is None:
                break
            yield record


def _group_sorted_records(records: Iterator[SortRecord]) -> Iterator[GroupedRecord]:
    current_token: Optional[bytes] = None
    current_rows: list[tuple[int, bytes]] = []
    for token, ordinal, payload in records:
        if current_token is None:
            current_token = token
        if token != current_token:
            yield current_token, current_rows
            current_token = token
            current_rows = []
        current_rows.append((ordinal, payload))
    if current_token is not None:
        yield current_token, current_rows


def _first_payload(rows: list[tuple[int, bytes]]) -> tuple[int, Any]:
    ordinal, payload = min(rows, key=lambda row: row[0])
    return ordinal, _from_blob(payload)


def _duplicate_payloads(rows: list[tuple[int, bytes]]) -> list[tuple[int, Any]]:
    return [(ordinal, _from_blob(payload)) for ordinal, payload in sorted(rows)[1:]]


def _make_temp_path(temp_dir: Optional[str], side: str) -> Path:
    base_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f"uniqdiff-{side}-", suffix=".sort", dir=str(base_dir))
        os.close(fd)
    except OSError as exc:
        raise TempStorageError(f"Cannot create temporary sort chunk in {base_dir!s}") from exc
    return Path(name)


def _check_disk_limit(paths: list[Path], disk_limit: Optional[Union[str, int]]) -> None:
    if disk_limit is None:
        return
    limit = parse_size(disk_limit)
    usage = sum(path.stat().st_size for path in paths if path.exists())
    if usage > limit:
        raise DiskLimitExceededError(
            f"Temporary external sort chunks exceeded disk_limit={disk_limit!r}"
        )


def _values_by_ordinal(rows: list[tuple[int, Any]]) -> list[Any]:
    return [value for _, value in sorted(rows, key=lambda row: row[0])]


def _file_mode_warnings(result_mode: str) -> list[str]:
    if result_mode != "file":
        return []
    return ["Result rows were streamed to output and are not materialized in memory."]
