import pytest

from uniqdiff import InvalidInputError, compare_sorted_iter, iter_sorted_diff


def test_iter_sorted_diff_streams_unique_rows():
    rows = list(iter_sorted_diff([1, 2, 4], [2, 3, 4], include_common=True))

    assert rows == [
        {"section": "only_in_first", "value": 1},
        {"section": "common", "value": 2},
        {"section": "only_in_second", "value": 3},
        {"section": "common", "value": 4},
    ]


def test_iter_sorted_diff_supports_keyed_rows_and_duplicates():
    left = [
        {"id": 1, "name": "Ann"},
        {"id": 2, "name": "Bob"},
        {"id": 2, "name": "Bob duplicate"},
        {"id": 4, "name": "Dana"},
    ]
    right = [
        {"id": 2, "name": "Bob new"},
        {"id": 3, "name": "Cara"},
        {"id": 3, "name": "Cara duplicate"},
        {"id": 4, "name": "Dana"},
    ]

    rows = list(
        iter_sorted_diff(
            left,
            right,
            key="id",
            include_common=True,
            include_duplicates=True,
        )
    )

    assert rows == [
        {"section": "only_in_first", "value": {"id": 1, "name": "Ann"}},
        {"section": "common", "value": {"id": 2, "name": "Bob"}},
        {"section": "duplicates_first", "value": {"id": 2, "name": "Bob duplicate"}},
        {"section": "only_in_second", "value": {"id": 3, "name": "Cara"}},
        {"section": "duplicates_second", "value": {"id": 3, "name": "Cara duplicate"}},
        {"section": "common", "value": {"id": 4, "name": "Dana"}},
    ]


def test_iter_sorted_diff_rejects_unsorted_input_by_default():
    with pytest.raises(InvalidInputError, match="sorted"):
        list(iter_sorted_diff([2, 1], [1, 2]))


def test_iter_sorted_diff_can_skip_sorted_validation():
    rows = list(iter_sorted_diff([1, 2], [2, 3], include_common=True, validate_sorted=False))

    assert rows == [
        {"section": "only_in_first", "value": 1},
        {"section": "common", "value": 2},
        {"section": "only_in_second", "value": 3},
    ]


def test_iter_sorted_diff_rejects_unorderable_tokens():
    with pytest.raises(InvalidInputError, match="orderable"):
        list(iter_sorted_diff([object()], [object()]))


def test_compare_sorted_iter_wraps_streaming_diff():
    rows = list(
        compare_sorted_iter(
            [{"id": 1}, {"id": 2}],
            [{"id": 2}, {"id": 3}],
            key="id",
            include_common=True,
        )
    )

    assert rows == [
        {"section": "only_in_first", "value": {"id": 1}},
        {"section": "common", "value": {"id": 2}},
        {"section": "only_in_second", "value": {"id": 3}},
    ]
