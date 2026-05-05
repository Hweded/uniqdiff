"""Core public comparison API."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Optional, Union

from uniqdiff._typing import KeySpec, Normalizer
from uniqdiff._utils import canonicalize
from uniqdiff.connectors import connect
from uniqdiff.disk import atomic_write_result
from uniqdiff.planner import build_duplicates_plan, build_execution_plan, disk_compare_backend
from uniqdiff.result import CompareResult, CompareStats
from uniqdiff.storage import (
    compare_memory,
    duplicates_external_sort,
    duplicates_memory,
    duplicates_partitions,
    duplicates_sqlite,
)
from uniqdiff.tokens import make_token_factory


def compare(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: KeySpec = None,
    normalizer: Optional[Normalizer] = None,
    strategy: str = "hash",
    mode: str = "memory",
    include_common: bool = False,
    include_duplicates: bool = False,
    include_stats: bool = True,
    chunk_size: int = 100_000,
    memory_limit: Optional[Union[str, int]] = None,
    temp_dir: Optional[str] = None,
    disk_limit: Optional[Union[str, int]] = None,
    disk_strategy: str = "sqlite",
    partition_count: Optional[int] = None,
    output: Optional[str] = None,
    result_mode: str = "memory",
    preserve_order: bool = True,
) -> CompareResult:
    """Compare two iterables and return their unique differences.

    The initial implementation is exact and memory-backed. The `mode`, `chunk_size`,
    `memory_limit`, `temp_dir`, and `disk_limit` parameters are part of the stable
    public contract for future out-of-core strategies.
    """

    plan = build_execution_plan(
        first,
        second,
        mode=mode,
        result_mode=result_mode,
        disk_strategy=disk_strategy,
        partition_count=partition_count,
        memory_limit=memory_limit,
        temp_dir=temp_dir,
        disk_limit=disk_limit,
        chunk_size=chunk_size,
        output=output,
        preserve_order=preserve_order,
        include_common=include_common,
        include_duplicates=include_duplicates,
    )
    token_factory = make_token_factory(key=key, normalizer=normalizer)

    if plan.use_disk:
        disk_compare = disk_compare_backend(plan.disk_strategy)
        extra_kwargs: dict[str, Any] = {}
        if plan.disk_strategy == "hash_partition":
            extra_kwargs["partition_count"] = plan.partition_count
        result = disk_compare(
            first,
            second,
            token_factory=token_factory,
            include_common=include_common,
            include_duplicates=include_duplicates,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
            mode=plan.mode,
            strategy=strategy,
            metadata=plan.metadata,
            output=output if plan.result_mode == "file" else None,
            result_mode=plan.result_mode,
            **extra_kwargs,
        )
        if not include_stats:
            result.stats = CompareStats()
        if output is not None and plan.result_mode == "memory":
            written = atomic_write_result(result, output)
            result.metadata["output"] = str(written)
        return result

    result = compare_memory(
        first,
        second,
        token_factory=token_factory,
        include_common=include_common,
        include_duplicates=include_duplicates,
        include_stats=include_stats,
        mode=plan.mode,
        strategy=strategy,
        metadata=plan.metadata,
        preserve_order=preserve_order,
    )
    if output is not None:
        written = atomic_write_result(result, output)
        result.metadata["output"] = str(written)

    return result


def diff(first: Iterable[Any], second: Iterable[Any], **kwargs: Any) -> CompareResult:
    """Return differences between two iterables."""

    kwargs.setdefault("include_common", False)
    return compare(first, second, **kwargs)


def unique(first: Iterable[Any], second: Iterable[Any], **kwargs: Any) -> list[Any]:
    """Return the combined list of elements found in only one iterable."""

    return compare(first, second, **kwargs).unique


def intersection(first: Iterable[Any], second: Iterable[Any], **kwargs: Any) -> list[Any]:
    """Return elements found in both iterables."""

    kwargs["include_common"] = True
    return compare(first, second, **kwargs).common or []


def duplicates(
    data: Iterable[Any],
    *,
    key: KeySpec = None,
    normalizer: Optional[Normalizer] = None,
    mode: str = "memory",
    chunk_size: int = 100_000,
    temp_dir: Optional[str] = None,
    disk_limit: Optional[Union[str, int]] = None,
    disk_strategy: str = "sqlite",
    partition_count: Optional[int] = None,
) -> list[Any]:
    """Return duplicate items from one iterable."""

    plan = build_duplicates_plan(
        data,
        mode=mode,
        disk_strategy=disk_strategy,
        partition_count=partition_count,
        chunk_size=chunk_size,
        temp_dir=temp_dir,
    )
    if plan.use_disk:
        token_factory = make_token_factory(key=key, normalizer=normalizer)
        if plan.disk_strategy == "hash_partition":
            return duplicates_partitions(
                data,
                token_factory=token_factory,
                chunk_size=chunk_size,
                temp_dir=temp_dir,
                disk_limit=disk_limit,
                partition_count=plan.partition_count,
            )
        if plan.disk_strategy == "external_sort":
            return duplicates_external_sort(
                data,
                token_factory=token_factory,
                chunk_size=chunk_size,
                temp_dir=temp_dir,
                disk_limit=disk_limit,
            )
        return duplicates_sqlite(
            data,
            token_factory=token_factory,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
        )
    token_factory = make_token_factory(key=key, normalizer=normalizer)
    return duplicates_memory(data, token_factory=token_factory)


def compare_by_key(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: Union[str, tuple[str, ...], list[str], Callable[[Any], Any]],
    **kwargs: Any,
) -> CompareResult:
    """Compare structured items by one key, several keys, or a key function."""

    return compare(first, second, key=key, strategy="key", **kwargs)


def compare_by_hash(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    algorithm: str = "sha256",
    normalizer: Optional[Normalizer] = None,
    **kwargs: Any,
) -> CompareResult:
    """Compare items by a stable cryptographic hash of their canonical representation."""

    def hash_key(item: Any) -> str:
        value = normalizer(item) if normalizer else item
        canonical = repr(canonicalize(value)).encode("utf-8")
        try:
            hasher = hashlib.new(algorithm)
        except ValueError as exc:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}") from exc
        hasher.update(canonical)
        return hasher.hexdigest()

    return compare(first, second, key=hash_key, strategy=f"hash:{algorithm}", **kwargs)


def compare_iter(first: Iterable[Any], second: Iterable[Any], **kwargs: Any) -> CompareResult:
    """Compare generic iterables or generators."""

    return compare(first, second, **kwargs)


def compare_files(
    file_a: str,
    file_b: str,
    *,
    format: str = "auto",
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
    **kwargs: Any,
) -> CompareResult:
    """Compare two supported files."""

    file_options = {
        "format": format,
        "encoding": encoding,
        "delimiter": delimiter,
        "quotechar": quotechar,
        "has_header": has_header,
        "fieldnames": fieldnames,
        "columns": columns,
        "batch_size": batch_size,
    }
    return compare_sources(
        file_a,
        file_b,
        first_kind="file",
        second_kind="file",
        first_options=file_options,
        second_options=file_options,
        **kwargs,
    )


def compare_streams(
    stream_a: Iterable[Any],
    stream_b: Iterable[Any],
    **kwargs: Any,
) -> CompareResult:
    """Compare file-like streams or already parsed streaming iterables."""

    return compare(stream_a, stream_b, **kwargs)


def compare_sources(
    first_source: Any,
    second_source: Any,
    *,
    first_kind: Optional[str] = None,
    second_kind: Optional[str] = None,
    first_options: Optional[dict[str, Any]] = None,
    second_options: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> CompareResult:
    """Compare two connector-backed sources."""

    first_connector = connect(first_source, kind=first_kind, **(first_options or {}))
    second_connector = connect(second_source, kind=second_kind, **(second_options or {}))
    result = compare(first_connector.open(), second_connector.open(), **kwargs)
    result.metadata["connectors"] = {
        "first": first_connector.describe(),
        "second": second_connector.describe(),
    }
    return result


def duplicates_source(
    source: Any,
    *,
    kind: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> list[Any]:
    """Find duplicates from a connector-backed source."""

    connector = connect(source, kind=kind, **(options or {}))
    return duplicates(connector.open(), **kwargs)

