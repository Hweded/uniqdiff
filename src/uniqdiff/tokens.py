"""Token extraction and normalization helpers for comparison backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from uniqdiff._typing import KeySpec, Normalizer
from uniqdiff._utils import canonicalize
from uniqdiff.exceptions import KeyExtractionError, NormalizationError

TokenFactory = Callable[[Any], Any]

_SCALAR_TOKEN_TYPES = {str, int, float, bool, bytes, type(None)}


def make_token_factory(
    *,
    key: KeySpec,
    normalizer: Optional[Normalizer],
) -> TokenFactory:
    """Compile key/normalizer settings into a per-item token function."""

    if key is None:
        if normalizer is None:
            return canonicalize_token

        def token_from_item(item: Any) -> Any:
            return _normalize_and_canonicalize(item, item=item, normalizer=normalizer)

        return token_from_item

    if isinstance(key, str):
        if normalizer is None:

            def token_from_str_key(item: Any) -> Any:
                return canonicalize_token(extract_str_key(item, key))

            return token_from_str_key

        def normalized_token_from_str_key(item: Any) -> Any:
            value = extract_str_key(item, key)
            return _normalize_and_canonicalize(value, item=item, normalizer=normalizer)

        return normalized_token_from_str_key

    if isinstance(key, (tuple, list)):
        parts = tuple(key)
        if normalizer is None and all(isinstance(part, str) for part in parts):

            def token_from_str_key_parts(item: Any) -> Any:
                if type(item) is dict:
                    try:
                        value = tuple(item[part] for part in parts)
                    except KeyError as exc:
                        raise KeyExtractionError(
                            f"Missing key {exc.args[0]!r} in item {item!r}"
                        ) from exc
                else:
                    value = tuple(extract_key(item, part) for part in parts)
                return value if _scalar_tuple(value) else canonicalize(value)

            return token_from_str_key_parts

        def token_from_key_parts(item: Any) -> Any:
            value = tuple(extract_key(item, part) for part in parts)
            if normalizer is not None:
                return _normalize_and_canonicalize(value, item=item, normalizer=normalizer)
            return canonicalize_token(value)

        return token_from_key_parts

    if callable(key):

        def token_from_callable(item: Any) -> Any:
            try:
                value = key(item)
            except Exception as exc:
                raise KeyExtractionError(f"Key function failed for item {item!r}") from exc
            if normalizer is not None:
                return _normalize_and_canonicalize(value, item=item, normalizer=normalizer)
            return canonicalize_token(value)

        return token_from_callable

    def invalid_key_token(item: Any) -> Any:
        return comparison_token(item, key=key, normalizer=normalizer)

    return invalid_key_token


def comparison_token(item: Any, *, key: KeySpec, normalizer: Optional[Normalizer]) -> Any:
    """Return a canonical comparison token for one item."""

    value = extract_key(item, key) if key is not None else item
    if normalizer is not None:
        try:
            value = normalizer(value)
        except Exception as exc:
            raise NormalizationError(f"Normalizer failed for item {item!r}") from exc
    return canonicalize_token(value)


def canonicalize_token(value: Any) -> Any:
    """Canonicalize token values while fast-pathing common scalar keys."""

    if type(value) in _SCALAR_TOKEN_TYPES:
        return value
    return canonicalize(value)


def _scalar_tuple(value: tuple[Any, ...]) -> bool:
    return all(type(part) in _SCALAR_TOKEN_TYPES for part in value)


def extract_key(item: Any, key: KeySpec) -> Any:
    """Extract a comparison key from an item."""

    if callable(key):
        try:
            return key(item)
        except Exception as exc:
            raise KeyExtractionError(f"Key function failed for item {item!r}") from exc

    if isinstance(key, (tuple, list)):
        return tuple(extract_key(item, part) for part in key)

    if not isinstance(key, str):
        raise KeyExtractionError("key must be a string, sequence of strings, callable, or None")

    return extract_str_key(item, key)


def extract_str_key(item: Any, key: str) -> Any:
    """Extract one named key from dict-like or attribute-based objects."""

    if type(item) is dict:
        try:
            return item[key]
        except KeyError as exc:
            raise KeyExtractionError(f"Missing key {key!r} in item {item!r}") from exc

    if isinstance(item, dict):
        try:
            return item[key]
        except KeyError as exc:
            raise KeyExtractionError(f"Missing key {key!r} in item {item!r}") from exc

    try:
        return getattr(item, key)
    except AttributeError as exc:
        raise KeyExtractionError(f"Missing attribute {key!r} in item {item!r}") from exc


def _normalize_and_canonicalize(
    value: Any,
    *,
    item: Any,
    normalizer: Normalizer,
) -> Any:
    try:
        normalized = normalizer(value)
    except Exception as exc:
        raise NormalizationError(f"Normalizer failed for item {item!r}") from exc
    return canonicalize_token(normalized)
