"""Hash partitioning disk backend."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections import defaultdict
from collections.abc import Callable, Iterable
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
PartitionRecord = tuple[bytes, int, bytes]


def compare_partitions(
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
    partition_count: int,
    output: Optional[str] = None,
    result_mode: str = "memory",
) -> CompareResult:
    """Compare two iterables by hashing records into temporary partition files."""

    _validate_partition_count(partition_count)
    paths = _create_partition_paths(temp_dir, partition_count)

    try:
        first_count = _write_partitions(
            first,
            paths.first,
            token_factory=token_factory,
            chunk_size=chunk_size,
            disk_limit=disk_limit,
            all_paths=[*paths.first, *paths.second],
        )
        second_count = _write_partitions(
            second,
            paths.second,
            token_factory=token_factory,
            chunk_size=chunk_size,
            disk_limit=disk_limit,
            all_paths=[*paths.first, *paths.second],
        )

        if result_mode == "file":
            return _write_file_result_from_partitions(
                paths,
                output=output,
                include_common=include_common,
                include_duplicates=include_duplicates,
                first_count=first_count,
                second_count=second_count,
                mode=mode,
                strategy=strategy,
                metadata=metadata,
                partition_count=partition_count,
            )

        only_first_rows: list[tuple[int, Any]] = []
        only_second_rows: list[tuple[int, Any]] = []
        common_rows: list[tuple[int, Any]] = []
        duplicates_first_rows: list[tuple[int, Any]] = []
        duplicates_second_rows: list[tuple[int, Any]] = []
        unique_first_count = 0
        unique_second_count = 0
        common_count = 0

        for left_path, right_path in zip(paths.first, paths.second):
            left = _read_partition(left_path)
            right = _read_partition(right_path)
            unique_first_count += len(left)
            unique_second_count += len(right)

            left_keys = set(left)
            right_keys = set(right)
            common_keys = left_keys & right_keys
            common_count += len(common_keys)

            for token, rows in left.items():
                first_row = min(rows, key=lambda row: row[0])
                if token not in right_keys:
                    only_first_rows.append((first_row[0], _from_blob(first_row[1])))
                elif include_common:
                    common_rows.append((first_row[0], _from_blob(first_row[1])))
                if include_duplicates and len(rows) > 1:
                    duplicates_first_rows.extend(
                        (ordinal, _from_blob(payload)) for ordinal, payload in sorted(rows)[1:]
                    )

            for token, rows in right.items():
                first_row = min(rows, key=lambda row: row[0])
                if token not in left_keys:
                    only_second_rows.append((first_row[0], _from_blob(first_row[1])))
                if include_duplicates and len(rows) > 1:
                    duplicates_second_rows.extend(
                        (ordinal, _from_blob(payload)) for ordinal, payload in sorted(rows)[1:]
                    )

        only_in_first = _values_by_ordinal(only_first_rows)
        only_in_second = _values_by_ordinal(only_second_rows)
        common = _values_by_ordinal(common_rows) if include_common else None
        duplicates_first = _values_by_ordinal(duplicates_first_rows) if include_duplicates else None
        duplicates_second = (
            _values_by_ordinal(duplicates_second_rows) if include_duplicates else None
        )
        stats = CompareStats(
            first_count=first_count,
            second_count=second_count,
            unique_first_count=unique_first_count,
            unique_second_count=unique_second_count,
            only_in_first_count=len(only_in_first),
            only_in_second_count=len(only_in_second),
            common_count=common_count,
            duplicate_first_count=0 if duplicates_first is None else len(duplicates_first),
            duplicate_second_count=0 if duplicates_second is None else len(duplicates_second),
            mode=mode,
            strategy=strategy,
        )

        return CompareResult(
            only_in_first=[] if result_mode == "file" else only_in_first,
            only_in_second=[] if result_mode == "file" else only_in_second,
            common=None if result_mode == "file" else common,
            unique=[] if result_mode == "file" else [*only_in_first, *only_in_second],
            duplicates_first=None if result_mode == "file" else duplicates_first,
            duplicates_second=None if result_mode == "file" else duplicates_second,
            stats=stats,
            metadata={
                **metadata,
                "backend": "hash_partition",
                "partition_count": partition_count,
                "output": output,
                "result_mode": result_mode,
                "partition_files_removed": True,
            },
            warnings=_file_mode_warnings(result_mode),
        )
    finally:
        for path in [*paths.first, *paths.second]:
            path.unlink(missing_ok=True)


def duplicates_partitions(
    data: Iterable[Any],
    *,
    token_factory: TokenFactory,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
    partition_count: int,
) -> list[Any]:
    """Find duplicates by processing one hash partition at a time."""

    _validate_partition_count(partition_count)
    paths = [_make_temp_path(temp_dir, "duplicates") for _ in range(partition_count)]

    try:
        _write_partitions(
            data,
            paths,
            token_factory=token_factory,
            chunk_size=chunk_size,
            disk_limit=disk_limit,
            all_paths=paths,
        )
        rows: list[tuple[int, Any]] = []
        for path in paths:
            partition = _read_partition(path)
            for values in partition.values():
                if len(values) > 1:
                    rows.extend(
                        (ordinal, _from_blob(payload))
                        for ordinal, payload in sorted(values)[1:]
                    )
        return _values_by_ordinal(rows)
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


class _PartitionPaths:
    def __init__(self, first: list[Path], second: list[Path]) -> None:
        self.first = first
        self.second = second


def _create_partition_paths(temp_dir: Optional[str], partition_count: int) -> _PartitionPaths:
    first = [_make_temp_path(temp_dir, "first") for _ in range(partition_count)]
    second = [_make_temp_path(temp_dir, "second") for _ in range(partition_count)]
    return _PartitionPaths(first=first, second=second)


def _make_temp_path(temp_dir: Optional[str], side: str) -> Path:
    base_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f"uniqdiff-{side}-", suffix=".part", dir=str(base_dir))
        os.close(fd)
    except OSError as exc:
        raise TempStorageError(f"Cannot create temporary partition in {base_dir!s}") from exc
    return Path(name)


def _write_file_result_from_partitions(
    paths: _PartitionPaths,
    *,
    output: Optional[str],
    include_common: bool,
    include_duplicates: bool,
    first_count: int,
    second_count: int,
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
    partition_count: int,
) -> CompareResult:
    if output is None:
        raise TempStorageError("result_mode='file' requires output")

    unique_first_count = 0
    unique_second_count = 0
    only_in_first_count = 0
    only_in_second_count = 0
    common_count = 0
    duplicate_first_count = 0
    duplicate_second_count = 0

    with StreamingResultWriter(output) as writer:
        for left_path, right_path in zip(paths.first, paths.second):
            left = _read_partition(left_path)
            right = _read_partition(right_path)
            unique_first_count += len(left)
            unique_second_count += len(right)

            left_keys = set(left)
            right_keys = set(right)
            common_keys = left_keys & right_keys
            common_count += len(common_keys)

            for token, rows in left.items():
                first_row = min(rows, key=lambda row: row[0])
                if token not in right_keys:
                    writer.write("only_in_first", _from_blob(first_row[1]))
                    only_in_first_count += 1
                elif include_common:
                    writer.write("common", _from_blob(first_row[1]))
                if include_duplicates and len(rows) > 1:
                    for _, payload in sorted(rows)[1:]:
                        writer.write("duplicates_first", _from_blob(payload))
                        duplicate_first_count += 1

            for token, rows in right.items():
                first_row = min(rows, key=lambda row: row[0])
                if token not in left_keys:
                    writer.write("only_in_second", _from_blob(first_row[1]))
                    only_in_second_count += 1
                if include_duplicates and len(rows) > 1:
                    for _, payload in sorted(rows)[1:]:
                        writer.write("duplicates_second", _from_blob(payload))
                        duplicate_second_count += 1

    return CompareResult(
        stats=CompareStats(
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
        ),
        metadata={
            **metadata,
            "backend": "hash_partition",
            "partition_count": partition_count,
            "output": output,
            "result_mode": "file",
            "partition_files_removed": True,
        },
        warnings=_file_mode_warnings("file"),
    )


def _write_partitions(
    items: Iterable[Any],
    paths: list[Path],
    *,
    token_factory: TokenFactory,
    chunk_size: int,
    disk_limit: Optional[Union[str, int]],
    all_paths: list[Path],
) -> int:
    handles = [path.open("wb") for path in paths]
    count = 0
    try:
        for item in items:
            token_blob = _to_blob(token_factory(item))
            partition = _partition_index(token_blob, len(paths))
            write_record(handles[partition], token_blob, count, _to_blob(item))
            count += 1
            if count % chunk_size == 0:
                _flush(handles)
                _check_disk_limit(all_paths, disk_limit)
        _flush(handles)
        _check_disk_limit(all_paths, disk_limit)
        return count
    finally:
        for handle in handles:
            handle.close()


def _read_partition(path: Path) -> dict[bytes, list[tuple[int, bytes]]]:
    rows: dict[bytes, list[tuple[int, bytes]]] = defaultdict(list)
    with path.open("rb") as file:
        while True:
            record = read_record(file)
            if record is None:
                break
            token, ordinal, payload = record
            rows[token].append((ordinal, payload))
    return dict(rows)


def _partition_index(token_blob: bytes, partition_count: int) -> int:
    digest = hashlib.blake2b(token_blob, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big") % partition_count


def _flush(handles: Iterable[Any]) -> None:
    for handle in handles:
        handle.flush()


def _check_disk_limit(paths: list[Path], disk_limit: Optional[Union[str, int]]) -> None:
    if disk_limit is None:
        return
    limit = parse_size(disk_limit)
    usage = sum(path.stat().st_size for path in paths if path.exists())
    if usage > limit:
        raise DiskLimitExceededError(
            f"Temporary hash partitions exceeded disk_limit={disk_limit!r}"
        )


def _validate_partition_count(partition_count: int) -> None:
    if partition_count <= 0:
        raise ValueError("partition_count must be greater than zero")


def _values_by_ordinal(rows: list[tuple[int, Any]]) -> list[Any]:
    return [value for _, value in sorted(rows, key=lambda row: row[0])]


def _file_mode_warnings(result_mode: str) -> list[str]:
    if result_mode != "file":
        return []
    return ["Result rows were streamed to output and are not materialized in memory."]
