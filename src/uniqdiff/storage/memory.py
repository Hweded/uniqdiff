"""Memory-backed exact comparison backend."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Optional

from uniqdiff.result import CompareResult, CompareStats
from uniqdiff.tokens import TokenFactory


def compare_memory(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    token_factory: TokenFactory,
    include_common: bool,
    include_duplicates: bool,
    include_stats: bool,
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
    preserve_order: bool,
) -> CompareResult:
    """Compare two iterables using in-memory indexes."""

    left = _index_items(
        first,
        token_factory=token_factory,
        collect_duplicates=include_duplicates,
    )
    right = _index_items(
        second,
        token_factory=token_factory,
        collect_duplicates=include_duplicates,
    )

    only_left_keys: Iterable[Any]
    only_right_keys: Iterable[Any]
    common_keys: Iterable[Any]
    if preserve_order:
        only_left_keys = [
            token for token in left.first_by_token if token not in right.first_by_token
        ]
        only_right_keys = [
            token for token in right.first_by_token if token not in left.first_by_token
        ]
        common_keys = [
            token for token in left.first_by_token if token in right.first_by_token
        ]
    else:
        left_keys = left.first_by_token.keys()
        right_keys = right.first_by_token.keys()
        only_left_keys = left_keys - right_keys
        only_right_keys = right_keys - left_keys
        common_keys = left_keys & right_keys

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
        common_count=len(common_keys),
        duplicate_first_count=0 if duplicates_first is None else len(duplicates_first),
        duplicate_second_count=0 if duplicates_second is None else len(duplicates_second),
        mode=mode,
        strategy=strategy,
    )

    return CompareResult(
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


def duplicates_memory(
    data: Iterable[Any],
    *,
    token_factory: TokenFactory,
) -> list[Any]:
    """Return duplicate values using an in-memory index."""

    index = _index_items(data, token_factory=token_factory, collect_duplicates=True)
    return index.duplicates or []


@dataclass
class _MemoryIndex:
    first_by_token: dict[Any, Any]
    item_count: int
    duplicates: Optional[list[Any]]


def _index_items(
    items: Iterable[Any],
    *,
    token_factory: TokenFactory,
    collect_duplicates: bool,
) -> _MemoryIndex:
    first_by_token: dict[Any, Any] = {}
    duplicate_values: Optional[dict[Any, list[Any]]] = (
        defaultdict(list) if collect_duplicates else None
    )
    item_count = 0
    for item in items:
        token = token_factory(item)
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
