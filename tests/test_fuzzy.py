import pytest

from uniqdiff import compare_fuzzy_strings, string_normalizer


def test_compare_fuzzy_strings_matches_similar_values():
    result = compare_fuzzy_strings(
        ["Alice Smith", "Bob"],
        ["alice smyth", "Cara"],
        threshold=75,
        normalizer=string_normalizer(lower=True, strip=True),
    )

    assert result.only_in_first == ["Bob"]
    assert result.only_in_second == ["Cara"]
    assert result.common is not None
    assert result.common[0]["first"] == "Alice Smith"
    assert result.common[0]["second"] == "alice smyth"
    assert result.common[0]["score"] >= 75
    assert result.metadata["strategy"] == "fuzzy"
    assert result.warnings


def test_compare_fuzzy_strings_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        compare_fuzzy_strings(["a"], ["b"], threshold=101)
