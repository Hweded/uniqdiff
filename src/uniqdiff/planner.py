"""Execution planning helpers for comparison engine calls."""

from __future__ import annotations

from collections.abc import Iterable, Sized
from dataclasses import dataclass
from typing import Any, Optional, Union, cast

from uniqdiff._utils import ensure_mode, parse_size
from uniqdiff.exceptions import InvalidInputError
from uniqdiff.output import ensure_result_mode
from uniqdiff.storage import compare_external_sort, compare_partitions, compare_sqlite
from uniqdiff.storage.protocols import CompareBackend

_AUTO_BYTES_PER_ITEM = 512
_AUTO_MEMORY_SAFETY_FACTOR = 0.70
_AUTO_SQLITE_ITEM_LIMIT = 1_000_000
_AUTO_HASH_PARTITION_ITEM_LIMIT = 20_000_000


@dataclass(frozen=True)
class ExecutionPlan:
    """Normalized execution settings for one comparison call."""

    mode: str
    result_mode: str
    disk_strategy: str
    partition_count: int
    use_disk: bool
    auto_decision: Optional[dict[str, Any]]
    metadata: dict[str, Any]


def build_execution_plan(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    mode: str,
    result_mode: str,
    disk_strategy: str,
    partition_count: Optional[int],
    memory_limit: Optional[Union[str, int]],
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
    chunk_size: int,
    output: Optional[str],
    preserve_order: bool,
    include_common: bool = False,
    include_duplicates: bool = False,
) -> ExecutionPlan:
    """Build a normalized plan for memory, disk, or auto comparison."""

    selected_mode = ensure_mode(mode)
    selected_result_mode = ensure_result_mode(result_mode)
    selected_disk_strategy = ensure_disk_strategy(disk_strategy)
    selected_partition_count = partition_count or 16

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if selected_result_mode == "file" and output is None:
        raise InvalidInputError("result_mode='file' requires output")
    if selected_result_mode == "file" and selected_mode == "memory":
        raise InvalidInputError("result_mode='file' requires mode='disk' or mode='auto'")

    auto_decision = auto_decision_for_sources(
        first,
        second,
        memory_limit=memory_limit,
        temp_dir=temp_dir,
        result_mode=selected_result_mode,
        disk_strategy=selected_disk_strategy,
        chunk_size=chunk_size,
        include_common=include_common,
        include_duplicates=include_duplicates,
        preserve_order=preserve_order,
        disk_limit=disk_limit,
    )
    use_disk = selected_mode == "disk" or (
        selected_mode == "auto" and auto_decision["use_disk"]
    )
    resolved_disk_strategy = (
        auto_decision["selected_disk_strategy"]
        if selected_disk_strategy == "auto"
        else selected_disk_strategy
    )

    metadata = {
        "backend": "memory",
        "chunk_size": chunk_size,
        "memory_limit": memory_limit,
        "temp_dir": temp_dir,
        "disk_limit": disk_limit,
        "disk_strategy": resolved_disk_strategy,
        "requested_disk_strategy": selected_disk_strategy,
        "partition_count": selected_partition_count,
        "result_mode": selected_result_mode,
        "preserve_order": preserve_order,
        "auto_decision": auto_decision if selected_mode == "auto" else None,
    }

    return ExecutionPlan(
        mode=selected_mode,
        result_mode=selected_result_mode,
        disk_strategy=resolved_disk_strategy,
        partition_count=selected_partition_count,
        use_disk=use_disk,
        auto_decision=auto_decision if selected_mode == "auto" else None,
        metadata=metadata,
    )


def build_duplicates_plan(
    data: Iterable[Any],
    *,
    mode: str,
    disk_strategy: str,
    partition_count: Optional[int],
    chunk_size: int,
    temp_dir: Optional[str],
) -> ExecutionPlan:
    """Build a normalized plan for duplicate detection."""

    selected_mode = ensure_mode(mode)
    selected_disk_strategy = ensure_disk_strategy(disk_strategy)
    selected_partition_count = partition_count or 16
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    decision = auto_decision_for_sources(
        data,
        (),
        memory_limit=None,
        temp_dir=temp_dir,
        result_mode="memory",
    )
    use_disk = selected_mode == "disk" or (
        selected_mode == "auto" and decision["use_disk"]
    )
    return ExecutionPlan(
        mode=selected_mode,
        result_mode="memory",
        disk_strategy=selected_disk_strategy,
        partition_count=selected_partition_count,
        use_disk=use_disk,
        auto_decision=decision if selected_mode == "auto" else None,
        metadata={},
    )


def ensure_disk_strategy(disk_strategy: str) -> str:
    """Normalize and validate disk backend strategy names."""

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
    if normalized not in {"sqlite", "hash_partition", "external_sort", "auto"}:
        raise InvalidInputError(
            "disk_strategy must be one of: 'sqlite', 'hash_partition', 'external_sort', 'auto'"
        )
    return normalized


def disk_compare_backend(disk_strategy: str) -> CompareBackend:
    """Return the backend function for a normalized disk strategy."""

    if disk_strategy == "hash_partition":
        return cast(CompareBackend, compare_partitions)
    if disk_strategy == "external_sort":
        return cast(CompareBackend, compare_external_sort)
    return cast(CompareBackend, compare_sqlite)


def auto_decision_for_sources(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    memory_limit: Optional[Union[str, int]],
    temp_dir: Optional[str],
    result_mode: str,
    disk_strategy: str = "sqlite",
    chunk_size: int = 100_000,
    include_common: bool = False,
    include_duplicates: bool = False,
    preserve_order: bool = True,
    disk_limit: Optional[Union[str, int]] = None,
) -> dict[str, Any]:
    """Decide whether auto mode should use memory or disk."""

    reasons: list[str] = []
    estimated_items = estimated_item_count(first, second)
    estimated_bytes = (
        estimated_items * _AUTO_BYTES_PER_ITEM if estimated_items is not None else None
    )
    base_decision: dict[str, Any] = {
        "estimated_items": estimated_items,
        "estimated_bytes": estimated_bytes,
        "bytes_per_item_estimate": _AUTO_BYTES_PER_ITEM,
        "memory_safety_factor": _AUTO_MEMORY_SAFETY_FACTOR,
        "requested_disk_strategy": disk_strategy,
        "selected_disk_strategy": _select_auto_disk_strategy(
            estimated_items=estimated_items,
            disk_strategy=disk_strategy,
            result_mode=result_mode,
            include_common=include_common,
            include_duplicates=include_duplicates,
            preserve_order=preserve_order,
            disk_limit=disk_limit,
        ),
        "chunk_size": chunk_size,
        "include_common": include_common,
        "include_duplicates": include_duplicates,
        "preserve_order": preserve_order,
        "disk_limit": disk_limit,
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
                reasons.append("estimated input size exceeds effective_memory_limit")
            else:
                reasons.append("estimated input size fits effective_memory_limit")
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


def estimated_item_count(*sources: Iterable[Any]) -> Optional[int]:
    """Return a cheap item estimate when all sources are sized."""

    total = 0
    for source in sources:
        if not isinstance(source, Sized):
            return None
        total += len(source)
    return total


def _select_auto_disk_strategy(
    *,
    estimated_items: Optional[int],
    disk_strategy: str,
    result_mode: str,
    include_common: bool,
    include_duplicates: bool,
    preserve_order: bool,
    disk_limit: Optional[Union[str, int]],
) -> str:
    if disk_strategy != "auto":
        return disk_strategy

    if result_mode == "file":
        return "sqlite"
    if preserve_order:
        return "sqlite"
    if disk_limit is not None:
        return "external_sort"
    if estimated_items is None:
        return "sqlite"
    if include_duplicates and estimated_items > _AUTO_SQLITE_ITEM_LIMIT:
        return "hash_partition"
    if include_common and estimated_items > _AUTO_HASH_PARTITION_ITEM_LIMIT:
        return "external_sort"
    if estimated_items > _AUTO_SQLITE_ITEM_LIMIT:
        return "hash_partition"
    return "sqlite"
