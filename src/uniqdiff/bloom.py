"""Probabilistic Bloom filter helpers."""

from __future__ import annotations

import hashlib
import math
import pickle
from collections.abc import Iterable
from typing import Any, Optional

from uniqdiff._typing import Normalizer
from uniqdiff._utils import canonicalize
from uniqdiff.result import CompareResult, CompareStats


class BloomFilter:
    """Small stdlib Bloom filter implementation.

    Bloom filters have no false negatives for inserted items, but they can produce
    false positives for unseen items.
    """

    def __init__(self, expected_items: int, false_positive_rate: float = 0.01) -> None:
        if expected_items <= 0:
            raise ValueError("expected_items must be greater than zero")
        if false_positive_rate <= 0 or false_positive_rate >= 1:
            raise ValueError("false_positive_rate must be between 0 and 1")

        bit_count = int(
            math.ceil(-(expected_items * math.log(false_positive_rate)) / (math.log(2) ** 2))
        )
        hash_count = max(1, int(round((bit_count / expected_items) * math.log(2))))

        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        self.bit_count = max(8, bit_count)
        self.hash_count = hash_count
        self._bits = bytearray((self.bit_count + 7) // 8)

    def add(self, value: Any) -> None:
        """Add a value to the filter."""

        for index in self._hashes(value):
            self._bits[index // 8] |= 1 << (index % 8)

    def __contains__(self, value: object) -> bool:
        return all(self._bits[index // 8] & (1 << (index % 8)) for index in self._hashes(value))

    def _hashes(self, value: Any) -> Iterable[int]:
        payload = pickle.dumps(canonicalize(value), protocol=4)
        for seed in range(self.hash_count):
            digest = hashlib.blake2b(
                payload,
                digest_size=8,
                person=seed.to_bytes(4, "big"),
            ).digest()
            yield int.from_bytes(digest, byteorder="big") % self.bit_count


def build_bloom_filter(
    data: Iterable[Any],
    *,
    expected_items: int,
    false_positive_rate: float = 0.01,
    normalizer: Optional[Normalizer] = None,
) -> BloomFilter:
    """Build a Bloom filter from an iterable."""

    bloom = BloomFilter(expected_items=expected_items, false_positive_rate=false_positive_rate)
    for item in data:
        bloom.add(_normalize(item, normalizer))
    return bloom


def probabilistic_diff_candidates(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    expected_first: int,
    expected_second: int,
    false_positive_rate: float = 0.01,
    normalizer: Optional[Normalizer] = None,
) -> CompareResult:
    """Return Bloom-filter candidates for unique differences.

    Results are approximate: false positives can suppress some true differences.
    """

    first_values = list(first)
    second_values = list(second)
    first_filter = build_bloom_filter(
        first_values,
        expected_items=expected_first,
        false_positive_rate=false_positive_rate,
        normalizer=normalizer,
    )
    second_filter = build_bloom_filter(
        second_values,
        expected_items=expected_second,
        false_positive_rate=false_positive_rate,
        normalizer=normalizer,
    )

    only_in_first = [
        item for item in first_values if _normalize(item, normalizer) not in second_filter
    ]
    only_in_second = [
        item for item in second_values if _normalize(item, normalizer) not in first_filter
    ]

    return CompareResult(
        only_in_first=only_in_first,
        only_in_second=only_in_second,
        unique=[*only_in_first, *only_in_second],
        stats=CompareStats(
            first_count=len(first_values),
            second_count=len(second_values),
            only_in_first_count=len(only_in_first),
            only_in_second_count=len(only_in_second),
            strategy="bloom",
        ),
        metadata={
            "backend": "memory",
            "strategy": "bloom",
            "false_positive_rate": false_positive_rate,
            "first_bit_count": first_filter.bit_count,
            "second_bit_count": second_filter.bit_count,
            "hash_count": first_filter.hash_count,
        },
        warnings=[
            "Bloom filter comparison is approximate and can hide true differences "
            "because of false positives.",
        ],
    )


def _normalize(value: Any, normalizer: Optional[Normalizer]) -> Any:
    return normalizer(value) if normalizer is not None else value
