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
    )
    use_disk = selected_mode == "disk" or (
        selected_mode == "auto" and auto_decision["use_disk"]
    )

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
        "auto_decision": auto_decision if selected_mode == "auto" else None,
    }

    return ExecutionPlan(
        mode=selected_mode,
        result_mode=selected_result_mode,
        disk_strategy=selected_disk_strategy,
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
    if normalized not in {"sqlite", "hash_partition", "external_sort"}:
        raise InvalidInputError(
            "disk_strategy must be one of: 'sqlite', 'hash_partition', 'external_sort'"
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
