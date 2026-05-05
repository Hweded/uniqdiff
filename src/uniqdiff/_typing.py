"""Shared typing helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from collections.abc import Iterable as TypingIterable
from os import PathLike
from typing import Any, Protocol, TextIO, Union

KeySpec = Union[str, tuple[str, ...], list[str], Callable[[Any], Any], None]
Normalizer = Callable[[Any], Any]
Comparator = Callable[[Any, Any], bool]
Source = Iterable[Any]
PathInput = Union[str, PathLike[str]]


class TextStream(Protocol):
    """Small protocol for readable text streams."""

    def read(self, size: int = -1) -> str:
        """Read text from the stream."""

    def __iter__(self) -> TypingIterable[str]:
        """Iterate over text lines."""


ReadableText = Union[TextIO, TextStream]
