"""Measurement helpers for benchmark adapters."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from benchmarks.comparison.models import ScenarioResult

T = TypeVar("T", bound=ScenarioResult)


def measure(call: Callable[[], T]) -> T:
    """Measure elapsed time and peak Python memory for an adapter call."""

    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = call()
    finally:
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    result.elapsed_seconds = round(elapsed, 6)
    result.peak_memory_bytes = peak
    return result


def file_size(path: str | Path | None) -> int:
    """Return file size if a path exists."""

    if path is None:
        return 0
    output = Path(path)
    if not output.exists():
        return 0
    return output.stat().st_size
