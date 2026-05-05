import pytest

from uniqdiff import BloomFilter, build_bloom_filter, probabilistic_diff_candidates


def test_bloom_filter_membership_for_inserted_items():
    bloom = BloomFilter(expected_items=10, false_positive_rate=0.01)
    bloom.add("alpha")
    bloom.add("beta")

    assert "alpha" in bloom
    assert "beta" in bloom


def test_build_bloom_filter_with_normalizer():
    bloom = build_bloom_filter(
        ["Alice"],
        expected_items=1,
        normalizer=lambda value: str(value).lower(),
    )

    assert "alice" in bloom


def test_probabilistic_diff_candidates_returns_safe_candidates():
    result = probabilistic_diff_candidates(
        [1, 2, 3],
        [3, 4],
        expected_first=3,
        expected_second=2,
        false_positive_rate=0.0001,
    )

    assert result.only_in_first == [1, 2]
    assert result.only_in_second == [4]
    assert result.metadata["strategy"] == "bloom"
    assert result.warnings


@pytest.mark.parametrize(
    ("expected_items", "false_positive_rate"),
    [(0, 0.01), (10, 0), (10, 1)],
)
def test_bloom_filter_rejects_invalid_parameters(expected_items, false_positive_rate):
    with pytest.raises(ValueError):
        BloomFilter(expected_items=expected_items, false_positive_rate=false_positive_rate)
