"""Reusable normalizers."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


def string_normalizer(
    *,
    lower: bool = False,
    strip: bool = True,
    remove_spaces: bool = False,
    remove_special: bool = False,
    cast: Callable[[Any], str] = str,
) -> Callable[[Any], str]:
    """Build a configurable string normalizer."""

    special_re = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+")

    def normalize(value: Any) -> str:
        text = cast(value)
        if strip:
            text = text.strip()
        if lower:
            text = text.lower()
        if remove_spaces:
            text = "".join(text.split())
        if remove_special:
            text = special_re.sub("", text)
        return text

    return normalize


def compose_normalizers(*normalizers: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose several normalizers into one function."""

    def normalize(value: Any) -> Any:
        result = value
        for normalizer in normalizers:
            result = normalizer(result)
        return result

    return normalize
