from dataclasses import dataclass

import pytest

from uniqdiff import (
    KeyExtractionError,
    compare,
    compare_by_hash,
    compare_by_key,
    duplicates,
    intersection,
    string_normalizer,
    unique,
)


def test_compare_simple_lists():
    result = compare([1, 2, 3], [3, 4, 5], include_common=True)

    assert result.only_in_first == [1, 2]
    assert result.only_in_second == [4, 5]
    assert result.common == [3]
    assert result.unique == [1, 2, 4, 5]
    assert result.stats.first_count == 3
    assert result.stats.second_count == 3


def test_unique_and_intersection_helpers():
    assert unique([1, 2], [2, 3]) == [1, 3]
    assert intersection([1, 2], [2, 3]) == [2]


def test_compare_dicts_by_key():
    old = [{"id": 1, "name": "Ann"}, {"id": 2, "name": "Bob"}]
    new = [{"id": 2, "name": "Bob"}, {"id": 3, "name": "Cara"}]

    result = compare_by_key(old, new, key="id")

    assert result.only_in_first == [{"id": 1, "name": "Ann"}]
    assert result.only_in_second == [{"id": 3, "name": "Cara"}]


def test_compare_by_multiple_keys():
    left = [{"country": "US", "id": 1}, {"country": "CA", "id": 1}]
    right = [{"country": "US", "id": 1}, {"country": "US", "id": 2}]

    result = compare_by_key(left, right, key=("country", "id"))

    assert result.only_in_first == [{"country": "CA", "id": 1}]
    assert result.only_in_second == [{"country": "US", "id": 2}]


def test_compare_dataclass_by_attribute():
    @dataclass
    class User:
        id: int
        name: str

    result = compare_by_key([User(1, "Ann")], [User(2, "Bob")], key="id")

    assert result.only_in_first == [User(1, "Ann")]
    assert result.only_in_second == [User(2, "Bob")]


def test_non_hashable_nested_structures_are_supported():
    left = [{"id": 1, "tags": ["a", "b"]}]
    right = [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": ["c"]}]

    result = compare(left, right)

    assert result.only_in_first == []
    assert result.only_in_second == [{"id": 2, "tags": ["c"]}]


def test_normalizer():
    normalizer = string_normalizer(lower=True, strip=True, remove_spaces=True)

    result = compare([" Alice ", "Bob"], ["alice", "Cara"], normalizer=normalizer)

    assert result.only_in_first == ["Bob"]
    assert result.only_in_second == ["Cara"]


def test_duplicates():
    assert duplicates(["a", "b", "a", "a"]) == ["a", "a"]


def test_compare_includes_duplicates():
    result = compare(["a", "a", "b"], ["b", "c", "c"], include_duplicates=True)

    assert result.duplicates_first == ["a"]
    assert result.duplicates_second == ["c"]
    assert result.stats.duplicate_first_count == 1
    assert result.stats.duplicate_second_count == 1


def test_compare_by_hash():
    result = compare_by_hash([{"a": 1}], [{"a": 1}, {"a": 2}])

    assert result.only_in_first == []
    assert result.only_in_second == [{"a": 2}]


def test_generator_input():
    result = compare((x for x in [1, 2, 3]), (x for x in [2, 3, 4]))

    assert result.only_in_first == [1]
    assert result.only_in_second == [4]


def test_missing_key_raises_clear_error():
    with pytest.raises(KeyExtractionError):
        compare_by_key([{"id": 1}], [{"name": "Bob"}], key="id")
