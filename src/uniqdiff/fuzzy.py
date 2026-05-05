"""Optional fuzzy string comparison helpers."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Optional

from uniqdiff._typing import Normalizer
from uniqdiff.result import CompareResult, CompareStats

try:  # pragma: no cover - depends on optional extra
    from rapidfuzz import fuzz as _rapidfuzz_fuzz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised through fallback behavior
    _rapidfuzz_fuzz = None


def compare_fuzzy_strings(
    first: list[str],
    second: list[str],
    *,
    threshold: float = 90.0,
    normalizer: Optional[Normalizer] = None,
) -> CompareResult:
    """Compare strings with greedy approximate matching.

    This helper is intentionally separate from exact comparison APIs. It is useful for
    small and medium string lists where `O(n*m)` matching is acceptable.
    """

    if threshold < 0 or threshold > 100:
        raise ValueError("threshold must be between 0 and 100")

    matched_second: set[int] = set()
    common: list[dict[str, Any]] = []
    only_in_first: list[str] = []

    normalized_second = [_normalize(value, normalizer) for value in second]
    for left in first:
        normalized_left = _normalize(left, normalizer)
        best_index: Optional[int] = None
        best_score = -1.0
        for index, normalized_right in enumerate(normalized_second):
            if index in matched_second:
                continue
            score = _score(normalized_left, normalized_right)
            if score > best_score:
                best_index = index
                best_score = score

        if best_index is not None and best_score >= threshold:
            matched_second.add(best_index)
            common.append(
                {
                    "first": left,
                    "second": second[best_index],
                    "score": round(best_score, 4),
                }
            )
        else:
            only_in_first.append(left)

    only_in_second = [value for index, value in enumerate(second) if index not in matched_second]

    return CompareResult(
        only_in_first=only_in_first,
        only_in_second=only_in_second,
        common=common,
        unique=[*only_in_first, *only_in_second],
        stats=CompareStats(
            first_count=len(first),
            second_count=len(second),
            unique_first_count=len(first),
            unique_second_count=len(second),
            only_in_first_count=len(only_in_first),
            only_in_second_count=len(only_in_second),
            common_count=len(common),
            strategy="fuzzy",
        ),
        metadata={
            "backend": "memory",
            "strategy": "fuzzy",
            "threshold": threshold,
            "scorer": "rapidfuzz.WRatio" if _rapidfuzz_fuzz is not None else "difflib.ratio",
        },
        warnings=[
            "Fuzzy comparison is approximate and uses greedy O(n*m) matching.",
        ],
    )


def _normalize(value: str, normalizer: Optional[Normalizer]) -> str:
    normalized = normalizer(value) if normalizer is not None else value
    return str(normalized)


def _score(first: str, second: str) -> float:
    if _rapidfuzz_fuzz is not None:  # pragma: no cover - optional extra
        return float(_rapidfuzz_fuzz.WRatio(first, second))
    return SequenceMatcher(None, first, second).ratio() * 100
