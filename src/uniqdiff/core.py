"""Core public comparison API."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence, Sized
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Optional, Union

from uniqdiff._typing import KeySpec, Normalizer
from uniqdiff._utils import canonicalize, ensure_mode, parse_size
from uniqdiff.connectors import connect
from uniqdiff.disk import atomic_write_result
from uniqdiff.exceptions import InvalidInputError, KeyExtractionError, NormalizationError
from uniqdiff.output import ensure_result_mode
from uniqdiff.result import CompareResult, CompareStats
from uniqdiff.storage import (
    compare_external_sort,
    compare_partitions,
    compare_sqlite,
    duplicates_external_sort,
    duplicates_partitions,
    duplicates_sqlite,
)

_AUTO_BYTES_PER_ITEM = 512
_AUTO_MEMORY_SAFETY_FACTOR = 0.70


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

    selected_mode = ensure_mode(mode)
    selected_result_mode = ensure_result_mode(result_mode)
    selected_disk_strategy = _ensure_disk_strategy(disk_strategy)
    selected_partition_count = partition_count or 16
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if selected_result_mode == "file" and output is None:
        raise InvalidInputError("result_mode='file' requires output")
    if selected_result_mode == "file" and selected_mode == "memory":
        raise InvalidInputError("result_mode='file' requires mode='disk' or mode='auto'")

    metadata = {
        "backend": "memory",
        "chunk_size": chunk_size,
        "memory_limit": memory_limit,
        "temp_dir": temp_dir,
        "disk_limit": disk_limit,
        "disk_strategy": selected_disk_strategy,
        "partition_count": selected_partition_count,
        "result_mode": selected_result_mode,
        "preserve_order": preserve_order,
    }
    auto_decision = _auto_decision(
        first,
        second,
        memory_limit=memory_limit,
        temp_dir=temp_dir,
        result_mode=selected_result_mode,
    )
    use_disk = selected_mode == "disk" or (selected_mode == "auto" and auto_decision["use_disk"])
    metadata["auto_decision"] = auto_decision if selected_mode == "auto" else None

    if use_disk:
        disk_compare = _disk_compare_backend(selected_disk_strategy)
        extra_kwargs: dict[str, Any] = {}
        if selected_disk_strategy == "hash_partition":
            extra_kwargs["partition_count"] = selected_partition_count
        result = disk_compare(
            first,
            second,
            token_factory=lambda item: _comparison_token(item, key=key, normalizer=normalizer),
            include_common=include_common,
            include_duplicates=include_duplicates,
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
            mode=selected_mode,
            strategy=strategy,
            metadata=metadata,
            output=output if selected_result_mode == "file" else None,
            result_mode=selected_result_mode,
            **extra_kwargs,
        )
        if not include_stats:
            result.stats = CompareStats()
        if output is not None and selected_result_mode == "memory":
            written = atomic_write_result(result, output)
            result.metadata["output"] = str(written)
        return result

    left = _index_items(
        first,
        key=key,
        normalizer=normalizer,
        collect_duplicates=include_duplicates,
    )
    right = _index_items(
        second,
        key=key,
        normalizer=normalizer,
        collect_duplicates=include_duplicates,
    )

    only_left_keys: list[Any] = []
    common_keys: list[Any] = []
    common_count = 0
    for token in left.first_by_token:
        if token in right.first_by_token:
            common_count += 1
            if include_common:
                common_keys.append(token)
        else:
            only_left_keys.append(token)

    only_right_keys = [
        token for token in right.first_by_token if token not in left.first_by_token
    ]

    only_in_first = _first_values(left.first_by_token, only_left_keys)
    only_in_second = _first_values(right.first_by_token, only_right_keys)
    common = _first_values(left.first_by_token, common_keys) if include_common else None

    duplicates_first = left.duplicates
    duplicates_second = right.duplicates

    stats = CompareStats(
        first_count=left.item_count,
        second_count=right.item_count,
        unique_first_count=len(left.first_by_token),
        unique_second_count=len(right.first_by_token),
        only_in_first_count=len(only_in_first),
        only_in_second_count=len(only_in_second),
        common_count=common_count,
        duplicate_first_count=0 if duplicates_first is None else len(duplicates_first),
        duplicate_second_count=0 if duplicates_second is None else len(duplicates_second),
        mode=selected_mode,
        strategy=strategy,
    )

    result = CompareResult(
        only_in_first=only_in_first,
        only_in_second=only_in_second,
        common=common,
        unique=[*only_in_first, *only_in_second],
        duplicates_first=duplicates_first,
        duplicates_second=duplicates_second,
        stats=stats if include_stats else CompareStats(),
        metadata=metadata,
        warnings=[],
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

    selected_mode = ensure_mode(mode)
    selected_disk_strategy = _ensure_disk_strategy(disk_strategy)
    selected_partition_count = partition_count or 16
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    auto_decision = _auto_decision(
        data,
        (),
        memory_limit=None,
        temp_dir=temp_dir,
        result_mode="memory",
    )
    if selected_mode == "disk" or (selected_mode == "auto" and auto_decision["use_disk"]):
        if selected_disk_strategy == "hash_partition":
            return duplicates_partitions(
                data,
                token_factory=lambda item: _comparison_token(item, key=key, normalizer=normalizer),
                chunk_size=chunk_size,
                temp_dir=temp_dir,
                disk_limit=disk_limit,
                partition_count=selected_partition_count,
            )
        if selected_disk_strategy == "external_sort":
            return duplicates_external_sort(
                data,
                token_factory=lambda item: _comparison_token(item, key=key, normalizer=normalizer),
                chunk_size=chunk_size,
                temp_dir=temp_dir,
                disk_limit=disk_limit,
            )
        return duplicates_sqlite(
            data,
            token_factory=lambda item: _comparison_token(item, key=key, normalizer=normalizer),
            chunk_size=chunk_size,
            temp_dir=temp_dir,
            disk_limit=disk_limit,
        )
    index = _index_items(data, key=key, normalizer=normalizer, collect_duplicates=True)
    return index.duplicates or []


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


@dataclass
class _MemoryIndex:
    first_by_token: dict[Any, Any]
    item_count: int
    duplicates: Optional[list[Any]]


def _index_items(
    items: Iterable[Any],
    *,
    key: KeySpec,
    normalizer: Optional[Normalizer],
    collect_duplicates: bool,
) -> _MemoryIndex:
    first_by_token: dict[Any, Any] = {}
    duplicate_values: Optional[dict[Any, list[Any]]] = (
        defaultdict(list) if collect_duplicates else None
    )
    item_count = 0
    for item in items:
        token = _comparison_token(item, key=key, normalizer=normalizer)
        if token in first_by_token:
            if duplicate_values is not None:
                duplicate_values[token].append(item)
        else:
            first_by_token[token] = item
        item_count += 1

    duplicates: Optional[list[Any]] = None
    if duplicate_values is not None:
        duplicates = []
        for token in first_by_token:
            duplicates.extend(duplicate_values.get(token, ()))

    return _MemoryIndex(
        first_by_token=first_by_token,
        item_count=item_count,
        duplicates=duplicates,
    )


def _first_values(first_by_token: dict[Any, Any], keys: Iterable[Any]) -> list[Any]:
    return [first_by_token[key] for key in keys]


def _comparison_token(item: Any, *, key: KeySpec, normalizer: Optional[Normalizer]) -> Any:
    value = _extract_key(item, key) if key is not None else item
    if normalizer is not None:
        try:
            value = normalizer(value)
        except Exception as exc:
            raise NormalizationError(f"Normalizer failed for item {item!r}") from exc
    return canonicalize(value)


def _extract_key(item: Any, key: KeySpec) -> Any:
    if callable(key):
        try:
            return key(item)
        except Exception as exc:
            raise KeyExtractionError(f"Key function failed for item {item!r}") from exc

    if isinstance(key, (tuple, list)):
        return tuple(_extract_key(item, part) for part in key)

    if not isinstance(key, str):
        raise KeyExtractionError("key must be a string, sequence of strings, callable, or None")

    source = asdict(item) if is_dataclass(item) and not isinstance(item, type) else item

    if isinstance(source, dict):
        try:
            return source[key]
        except KeyError as exc:
            raise KeyExtractionError(f"Missing key {key!r} in item {item!r}") from exc

    try:
        return getattr(source, key)
    except AttributeError as exc:
        raise KeyExtractionError(f"Missing attribute {key!r} in item {item!r}") from exc


def _ensure_disk_strategy(disk_strategy: str) -> str:
    normalized = disk_strategy.lower().replace("-", "_")
    aliases = {
        "partition": "hash_partition",
        "hash": "hash_partition",
        "hash_partitioning": "hash_partition",
        "external": "external_sort",
        "sort": "external_sort",
        "external-sort": "external_sort",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"sqlite", "hash_partition", "external_sort"}:
        raise InvalidInputError(
            "disk_strategy must be one of: 'sqlite', 'hash_partition', 'external_sort'"
        )
    return normalized


def _disk_compare_backend(disk_strategy: str) -> Callable[..., CompareResult]:
    if disk_strategy == "hash_partition":
        return compare_partitions
    if disk_strategy == "external_sort":
        return compare_external_sort
    return compare_sqlite


def _auto_decision(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    memory_limit: Optional[Union[str, int]],
    temp_dir: Optional[str],
    result_mode: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    estimated_items = _estimated_item_count(first, second)
    estimated_bytes = (
        estimated_items * _AUTO_BYTES_PER_ITEM if estimated_items is not None else None
    )
    base_decision: dict[str, Any] = {
        "estimated_items": estimated_items,
        "estimated_bytes": estimated_bytes,
        "bytes_per_item_estimate": _AUTO_BYTES_PER_ITEM,
        "memory_safety_factor": _AUTO_MEMORY_SAFETY_FACTOR,
    }

    if result_mode == "file":
        reasons.append("result_mode='file'")
        return {
            **base_decision,
            "use_disk": True,
            "reason": ", ".join(reasons),
            "selected_backend": "disk",
        }

    if temp_dir is not None:
        reasons.append("temp_dir provided")
        return {
            **base_decision,
            "use_disk": True,
            "reason": ", ".join(reasons),
            "selected_backend": "disk",
        }

    if memory_limit is not None:
        limit_bytes = parse_size(memory_limit)
        effective_limit = int(limit_bytes * _AUTO_MEMORY_SAFETY_FACTOR)
        if estimated_bytes is None:
            reasons.append("memory_limit provided for unsized input")
            use_disk = True
        else:
            use_disk = estimated_bytes > effective_limit
            if use_disk:
                reasons.append("estimated input size exceeds effective memory_limit")
            else:
                reasons.append("estimated input size fits effective memory_limit")
        return {
            **base_decision,
            "use_disk": use_disk,
            "reason": ", ".join(reasons),
            "memory_limit_bytes": limit_bytes,
            "effective_memory_limit_bytes": effective_limit,
            "selected_backend": "disk" if use_disk else "memory",
        }

    return {
        **base_decision,
        "use_disk": False,
        "reason": "default memory backend",
        "selected_backend": "memory",
    }


def _estimated_item_count(*sources: Iterable[Any]) -> Optional[int]:
    total = 0
    for source in sources:
        if not isinstance(source, Sized):
            return None
        total += len(source)
    return total
