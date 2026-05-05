"""Streaming comparison helpers for already sorted inputs."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Optional

from uniqdiff._typing import KeySpec, Normalizer
from uniqdiff.exceptions import InvalidInputError
from uniqdiff.tokens import TokenFactory, make_token_factory

ResultRow = dict[str, Any]


@dataclass
class _TokenGroup:
    token: Any
    values: list[Any]


def iter_sorted_diff(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    key: KeySpec = None,
    normalizer: Optional[Normalizer] = None,
    include_common: bool = False,
    include_duplicates: bool = False,
    validate_sorted: bool = True,
) -> Iterator[ResultRow]:
    """Yield exact diff rows for inputs already sorted by comparison token.

    This helper does not build an in-memory index and does not write temporary
    files. It keeps only the current equal-token group from each input in memory.

    Both inputs must be sorted by the same token produced from `key` and
    `normalizer`. When `validate_sorted=True`, descending tokens raise
    `InvalidInputError`.
    """

    token_factory = make_token_factory(key=key, normalizer=normalizer)
    left_groups = _group_sorted(first, token_factory=token_factory, validate=validate_sorted)
    right_groups = _group_sorted(second, token_factory=token_factory, validate=validate_sorted)

    left_item = next(left_groups, None)
    right_item = next(right_groups, None)
    while left_item is not None or right_item is not None:
        if right_item is None or (
            left_item is not None and _token_less(left_item.token, right_item.token)
        ):
            if left_item is None:
                raise RuntimeError("Streaming merge reached an invalid left state")
            yield _row("only_in_first", left_item.values[0])
            if include_duplicates:
                yield from _duplicate_rows("duplicates_first", left_item.values)
            left_item = next(left_groups, None)
            continue

        if left_item is None or _token_less(right_item.token, left_item.token):
            yield _row("only_in_second", right_item.values[0])
            if include_duplicates:
                yield from _duplicate_rows("duplicates_second", right_item.values)
            right_item = next(right_groups, None)
            continue

        if include_common:
            yield _row("common", left_item.values[0])
        if include_duplicates:
            yield from _duplicate_rows("duplicates_first", left_item.values)
            yield from _duplicate_rows("duplicates_second", right_item.values)
        left_item = next(left_groups, None)
        right_item = next(right_groups, None)


def _group_sorted(
    items: Iterable[Any],
    *,
    token_factory: TokenFactory,
    validate: bool,
) -> Iterator[_TokenGroup]:
    current_token: Any = None
    current_values: list[Any] = []
    has_current = False

    for item in items:
        token = token_factory(item)
        if not has_current:
            current_token = token
            current_values = [item]
            has_current = True
            continue

        if token == current_token:
            current_values.append(item)
            continue

        if validate and _token_less(token, current_token):
            raise InvalidInputError(
                "iter_sorted_diff requires inputs sorted by the comparison token"
            )

        yield _TokenGroup(token=current_token, values=current_values)
        current_token = token
        current_values = [item]

    if has_current:
        yield _TokenGroup(token=current_token, values=current_values)


def _token_less(left: Any, right: Any) -> bool:
    try:
        return bool(left < right)
    except TypeError as exc:
        raise InvalidInputError(
            "iter_sorted_diff requires orderable comparison tokens; pass key=... "
            "or pre-normalize inputs to sortable tokens"
        ) from exc


def _row(section: str, value: Any) -> ResultRow:
    return {"section": section, "value": value}


def _duplicate_rows(section: str, values: list[Any]) -> Iterator[ResultRow]:
    for value in values[1:]:
        yield _row(section, value)
