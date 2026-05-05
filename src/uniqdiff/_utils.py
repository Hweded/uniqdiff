"""Internal utility helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, Union

from uniqdiff.exceptions import InvalidInputError


def ensure_mode(mode: str) -> str:
    """Validate and normalize processing mode."""

    normalized = mode.lower()
    if normalized not in {"memory", "disk", "auto"}:
        raise InvalidInputError("mode must be one of: 'memory', 'disk', 'auto'")
    return normalized


def parse_size(value: Union[str, int]) -> int:
    """Parse human-friendly byte sizes such as 512MB or 2GB."""

    if isinstance(value, int):
        return value

    text = value.strip().upper()
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }
    for suffix, multiplier in sorted(units.items(), key=lambda item: len(item[0]), reverse=True):
        if text.endswith(suffix):
            number = text[: -len(suffix)].strip()
            return int(float(number) * multiplier)
    return int(text)


def canonicalize(value: Any) -> Any:
    """Convert nested Python data to a stable hashable representation."""

    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)

    if isinstance(value, Mapping):
        return tuple(sorted((canonicalize(key), canonicalize(item)) for key, item in value.items()))

    if isinstance(value, tuple):
        return tuple(canonicalize(item) for item in value)

    if isinstance(value, list):
        return tuple(canonicalize(item) for item in value)

    if isinstance(value, set):
        return frozenset(canonicalize(item) for item in value)

    try:
        hash(value)
    except TypeError:
        return repr(value)

    return value


def first_values(groups: dict[Any, list[Any]], keys: Iterable[Any]) -> list[Any]:
    """Return the first original value for each key."""

    return [groups[key][0] for key in keys]
