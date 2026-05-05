from collections import Counter
from pathlib import Path

import pytest

from uniqdiff import (
    DiskLimitExceededError,
    compare,
    compare_by_key,
    compare_files,
    compare_sources,
    duplicates,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEMP_DIR = str(FIXTURES)


def test_disk_mode_compare_lists():
    result = compare(
        [1, 2, 2, 3],
        [2, 3, 4, 4],
        mode="disk",
        temp_dir=TEMP_DIR,
        include_common=True,
        include_duplicates=True,
        chunk_size=2,
    )

    assert result.only_in_first == [1]
    assert result.only_in_second == [4]
    assert result.common == [2, 3]
    assert result.duplicates_first == [2]
    assert result.duplicates_second == [4]
    assert result.metadata["backend"] == "sqlite"
    assert result.stats.mode == "disk"


def test_hash_partition_disk_strategy_compare_lists():
    result = compare(
        [1, 2, 2, 3, 5],
        [2, 3, 4, 4],
        mode="disk",
        disk_strategy="hash_partition",
        partition_count=3,
        temp_dir=TEMP_DIR,
        include_common=True,
        include_duplicates=True,
        chunk_size=2,
    )

    assert result.only_in_first == [1, 5]
    assert result.only_in_second == [4]
    assert result.common == [2, 3]
    assert result.duplicates_first == [2]
    assert result.duplicates_second == [4]
    assert result.metadata["backend"] == "hash_partition"
    assert result.metadata["partition_count"] == 3


def test_external_sort_disk_strategy_compare_lists():
    result = compare(
        [5, 1, 2, 2, 3],
        [4, 2, 3, 4],
        mode="disk",
        disk_strategy="external_sort",
        temp_dir=TEMP_DIR,
        include_common=True,
        include_duplicates=True,
        chunk_size=2,
    )

    assert result.only_in_first == [5, 1]
    assert result.only_in_second == [4]
    assert result.common == [2, 3]
    assert result.duplicates_first == [2]
    assert result.duplicates_second == [4]
    assert result.metadata["backend"] == "external_sort"
    assert result.metadata["left_chunk_count"] == 3
    assert result.metadata["right_chunk_count"] == 2


@pytest.mark.parametrize("disk_strategy", ["sqlite", "hash_partition", "external_sort"])
def test_compare_by_key_is_consistent_across_disk_strategies(disk_strategy):
    left = [{"id": 1, "name": "Ann"}, {"id": 2, "name": "Bob"}]
    right = [{"id": 2, "name": "Bob"}, {"id": 3, "name": "Cara"}]

    result = compare_by_key(
        left,
        right,
        key="id",
        mode="disk",
        disk_strategy=disk_strategy,
        partition_count=4,
        temp_dir=TEMP_DIR,
        chunk_size=1,
        include_common=True,
    )

    assert result.only_in_first == [{"id": 1, "name": "Ann"}]
    assert result.only_in_second == [{"id": 3, "name": "Cara"}]
    assert result.common == [{"id": 2, "name": "Bob"}]


@pytest.mark.parametrize("disk_strategy", ["sqlite", "hash_partition", "external_sort"])
def test_compare_sources_is_consistent_across_disk_strategies(disk_strategy):
    result = compare_sources(
        FIXTURES / "left.csv",
        FIXTURES / "right.csv",
        first_kind="csv",
        second_kind="csv",
        key="id",
        mode="disk",
        disk_strategy=disk_strategy,
        partition_count=4,
        temp_dir=TEMP_DIR,
        chunk_size=1,
    )

    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]
    assert result.metadata["connectors"]["first"]["connector"] == "csv"


@pytest.mark.parametrize(
    ("mode", "disk_strategy"),
    [
        ("memory", "sqlite"),
        ("auto", "sqlite"),
        ("disk", "sqlite"),
        ("disk", "hash_partition"),
        ("disk", "external_sort"),
    ],
)
def test_empty_inputs_are_stable_across_modes(mode, disk_strategy):
    result = compare(
        [],
        [],
        mode=mode,
        disk_strategy=disk_strategy,
        temp_dir=TEMP_DIR if mode == "disk" else None,
        include_common=True,
        include_duplicates=True,
    )

    assert result.only_in_first == []
    assert result.only_in_second == []
    assert result.common == []
    assert result.duplicates_first == []
    assert result.duplicates_second == []


def test_disk_mode_accepts_generators():
    result = compare(
        (item for item in [{"id": 1}, {"id": 2}]),
        (item for item in [{"id": 2}, {"id": 3}]),
        key="id",
        mode="disk",
        temp_dir=TEMP_DIR,
    )

    assert result.only_in_first == [{"id": 1}]
    assert result.only_in_second == [{"id": 3}]


def test_auto_mode_uses_sqlite_when_temp_dir_is_given():
    result = compare([1, 2], [2, 3], mode="auto", temp_dir=TEMP_DIR)

    assert result.metadata["backend"] == "sqlite"
    assert result.metadata["auto_decision"]["reason"] == "temp_dir provided"
    assert result.only_in_first == [1]
    assert result.only_in_second == [3]


def test_auto_mode_uses_memory_when_estimate_fits_memory_limit():
    result = compare([1, 2], [2, 3], mode="auto", memory_limit="1MB")

    assert result.metadata["backend"] == "memory"
    assert result.metadata["auto_decision"]["use_disk"] is False
    assert result.metadata["auto_decision"]["selected_backend"] == "memory"
    assert result.metadata["auto_decision"]["bytes_per_item_estimate"] > 0
    assert result.metadata["auto_decision"]["effective_memory_limit_bytes"] > 0
    assert result.only_in_first == [1]
    assert result.only_in_second == [3]


def test_auto_mode_uses_disk_when_estimate_exceeds_memory_limit():
    result = compare([1, 2], [2, 3], mode="auto", memory_limit="1B")

    assert result.metadata["backend"] == "sqlite"
    assert result.metadata["auto_decision"]["use_disk"] is True
    assert result.metadata["auto_decision"]["selected_backend"] == "disk"
    assert result.metadata["auto_decision"]["memory_limit_bytes"] == 1
    assert result.metadata["auto_decision"]["effective_memory_limit_bytes"] == 0
    assert result.only_in_first == [1]
    assert result.only_in_second == [3]


def test_auto_mode_uses_disk_for_unsized_input_with_memory_limit():
    result = compare(
        (item for item in [1, 2]),
        (item for item in [2, 3]),
        mode="auto",
        memory_limit="1MB",
    )

    assert result.metadata["backend"] == "sqlite"
    assert result.metadata["auto_decision"]["estimated_items"] is None
    assert result.only_in_first == [1]
    assert result.only_in_second == [3]


def test_disk_mode_compare_files():
    result = compare_files(
        str(FIXTURES / "left.csv"),
        str(FIXTURES / "right.csv"),
        format="csv",
        key="id",
        mode="disk",
        temp_dir=TEMP_DIR,
    )

    assert result.metadata["backend"] == "sqlite"
    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_hash_partition_compare_files():
    result = compare_files(
        str(FIXTURES / "left.csv"),
        str(FIXTURES / "right.csv"),
        format="csv",
        key="id",
        mode="disk",
        disk_strategy="hash_partition",
        partition_count=4,
        temp_dir=TEMP_DIR,
    )

    assert result.metadata["backend"] == "hash_partition"
    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_external_sort_compare_files():
    result = compare_files(
        str(FIXTURES / "left.csv"),
        str(FIXTURES / "right.csv"),
        format="csv",
        key="id",
        mode="disk",
        disk_strategy="external_sort",
        temp_dir=TEMP_DIR,
        chunk_size=1,
    )

    assert result.metadata["backend"] == "external_sort"
    assert result.only_in_first == [{"id": "1", "name": "Ann"}]
    assert result.only_in_second == [{"id": "3", "name": "Cara"}]


def test_duplicates_disk_mode():
    result = duplicates(["a", "b", "a", "c", "b"], mode="disk", temp_dir=TEMP_DIR, chunk_size=2)

    assert result == ["a", "b"]


def test_duplicates_hash_partition_mode():
    result = duplicates(
        ["a", "b", "a", "c", "b"],
        mode="disk",
        disk_strategy="hash_partition",
        partition_count=2,
        temp_dir=TEMP_DIR,
        chunk_size=2,
    )

    assert result == ["a", "b"]


def test_duplicates_external_sort_mode():
    result = duplicates(
        ["b", "a", "b", "c", "a"],
        mode="disk",
        disk_strategy="external_sort",
        temp_dir=TEMP_DIR,
        chunk_size=2,
    )

    assert result == ["b", "a"]


def test_disk_limit_is_enforced():
    with pytest.raises(DiskLimitExceededError):
        compare(
            [{"id": item, "payload": "x" * 100} for item in range(20)],
            [],
            key="id",
            mode="disk",
            temp_dir=TEMP_DIR,
            disk_limit=1,
        )


def test_hash_partition_disk_limit_is_enforced():
    with pytest.raises(DiskLimitExceededError):
        compare(
            [{"id": item, "payload": "x" * 100} for item in range(20)],
            [],
            key="id",
            mode="disk",
            disk_strategy="hash_partition",
            partition_count=2,
            temp_dir=TEMP_DIR,
            disk_limit=1,
        )


def test_external_sort_disk_limit_is_enforced():
    with pytest.raises(DiskLimitExceededError):
        compare(
            [{"id": item, "payload": "x" * 100} for item in range(20)],
            [],
            key="id",
            mode="disk",
            disk_strategy="external_sort",
            temp_dir=TEMP_DIR,
            disk_limit=1,
        )


@pytest.mark.parametrize(
    ("mode", "disk_strategy", "memory_limit"),
    [
        ("memory", "sqlite", None),
        ("disk", "sqlite", None),
        ("disk", "hash_partition", None),
        ("disk", "external_sort", None),
        ("auto", "sqlite", "1B"),
    ],
)
def test_backend_equivalence_for_structured_rows(mode, disk_strategy, memory_limit):
    left = [
        {"id": 1, "name": "Ann"},
        {"id": 2, "name": "Bob"},
        {"id": 2, "name": "Bob duplicate"},
        {"id": 4, "name": "Dana"},
    ]
    right = [
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Cara"},
        {"id": 3, "name": "Cara duplicate"},
        {"id": 4, "name": "Dana"},
    ]

    baseline = compare(
        left,
        right,
        key="id",
        include_common=True,
        include_duplicates=True,
    )
    result = compare(
        left,
        right,
        key="id",
        mode=mode,
        disk_strategy=disk_strategy,
        memory_limit=memory_limit,
        partition_count=4,
        temp_dir=TEMP_DIR if mode == "disk" else None,
        include_common=True,
        include_duplicates=True,
        chunk_size=1,
    )

    assert result.only_in_first == baseline.only_in_first
    assert result.only_in_second == baseline.only_in_second
    assert result.common == baseline.common
    assert result.unique == baseline.unique
    assert result.duplicates_first == baseline.duplicates_first
    assert result.duplicates_second == baseline.duplicates_second
    assert result.stats.only_in_first_count == baseline.stats.only_in_first_count
    assert result.stats.only_in_second_count == baseline.stats.only_in_second_count
    assert result.stats.common_count == baseline.stats.common_count
    assert result.stats.duplicate_first_count == baseline.stats.duplicate_first_count
    assert result.stats.duplicate_second_count == baseline.stats.duplicate_second_count


@pytest.mark.parametrize("disk_strategy", ["sqlite", "hash_partition", "external_sort"])
def test_duplicates_backend_equivalence(disk_strategy):
    data = ["a", "b", "a", "c", "b", "d", "a"]

    result = duplicates(
        data,
        mode="disk",
        disk_strategy=disk_strategy,
        partition_count=4,
        temp_dir=TEMP_DIR,
        chunk_size=2,
    )

    assert Counter(result) == Counter(duplicates(data))
