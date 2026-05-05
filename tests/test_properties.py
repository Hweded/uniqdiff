from collections import Counter
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from uniqdiff import compare, duplicates, string_normalizer

TEMP_DIR = str(Path(__file__).parent / "fixtures")
INT_LISTS = st.lists(st.integers(min_value=-20, max_value=20), max_size=25)
TEXT_LISTS = st.lists(st.text(min_size=0, max_size=8), max_size=20)


def _projection(result):
    return {
        "only_in_first": result.only_in_first,
        "only_in_second": result.only_in_second,
        "common": result.common,
        "unique": result.unique,
        "stats": {
            "first_count": result.stats.first_count,
            "second_count": result.stats.second_count,
            "unique_first_count": result.stats.unique_first_count,
            "unique_second_count": result.stats.unique_second_count,
            "only_in_first_count": result.stats.only_in_first_count,
            "only_in_second_count": result.stats.only_in_second_count,
            "common_count": result.stats.common_count,
            "duplicate_first_count": result.stats.duplicate_first_count,
            "duplicate_second_count": result.stats.duplicate_second_count,
        },
    }


def _duplicate_projection(values):
    return Counter(values or [])


@given(INT_LISTS, INT_LISTS)
@settings(max_examples=50, deadline=None)
def test_disk_backends_match_memory_for_int_lists(first, second):
    memory = compare(first, second, include_common=True, include_duplicates=True)

    for disk_strategy in ("sqlite", "hash_partition", "external_sort"):
        disk = compare(
            first,
            second,
            mode="disk",
            disk_strategy=disk_strategy,
            partition_count=4,
            temp_dir=TEMP_DIR,
            chunk_size=5,
            include_common=True,
            include_duplicates=True,
        )
        assert _projection(disk) == _projection(memory)
        assert _duplicate_projection(disk.duplicates_first) == _duplicate_projection(
            memory.duplicates_first
        )
        assert _duplicate_projection(disk.duplicates_second) == _duplicate_projection(
            memory.duplicates_second
        )


@given(INT_LISTS)
@settings(max_examples=50, deadline=None)
def test_duplicate_backends_match_memory(data):
    memory = duplicates(data)

    for disk_strategy in ("sqlite", "hash_partition", "external_sort"):
        disk = duplicates(
            data,
            mode="disk",
            disk_strategy=disk_strategy,
            partition_count=4,
            temp_dir=TEMP_DIR,
            chunk_size=5,
        )
        assert Counter(disk) == Counter(memory)


@given(TEXT_LISTS, TEXT_LISTS)
@settings(max_examples=30, deadline=None)
def test_normalized_disk_backends_match_memory(first, second):
    normalizer = string_normalizer(lower=True, strip=True)
    memory = compare(
        first,
        second,
        normalizer=normalizer,
        include_common=True,
        include_duplicates=True,
    )

    for disk_strategy in ("sqlite", "hash_partition", "external_sort"):
        disk = compare(
            first,
            second,
            normalizer=normalizer,
            mode="disk",
            disk_strategy=disk_strategy,
            partition_count=4,
            temp_dir=TEMP_DIR,
            chunk_size=5,
            include_common=True,
            include_duplicates=True,
        )
        assert _projection(disk) == _projection(memory)
        assert _duplicate_projection(disk.duplicates_first) == _duplicate_projection(
            memory.duplicates_first
        )
        assert _duplicate_projection(disk.duplicates_second) == _duplicate_projection(
            memory.duplicates_second
        )
