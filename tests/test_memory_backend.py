from uniqdiff.storage.memory import compare_memory, duplicates_memory
from uniqdiff.tokens import make_token_factory


def test_compare_memory_backend_preserves_order_by_default():
    token_factory = make_token_factory(key=None, normalizer=None)

    result = compare_memory(
        [3, 1, 2],
        [2, 4],
        token_factory=token_factory,
        include_common=True,
        include_duplicates=False,
        include_stats=True,
        mode="memory",
        strategy="hash",
        metadata={"backend": "memory"},
        preserve_order=True,
    )

    assert result.only_in_first == [3, 1]
    assert result.only_in_second == [4]
    assert result.common == [2]
    assert result.stats.common_count == 1


def test_compare_memory_backend_can_skip_order_preservation():
    token_factory = make_token_factory(key=None, normalizer=None)

    result = compare_memory(
        [3, 1, 2],
        [2, 4],
        token_factory=token_factory,
        include_common=True,
        include_duplicates=False,
        include_stats=True,
        mode="memory",
        strategy="hash",
        metadata={"backend": "memory"},
        preserve_order=False,
    )

    assert set(result.only_in_first) == {1, 3}
    assert result.only_in_second == [4]
    assert result.common == [2]


def test_duplicates_memory_backend():
    token_factory = make_token_factory(key=None, normalizer=None)

    assert duplicates_memory(["a", "b", "a", "a"], token_factory=token_factory) == [
        "a",
        "a",
    ]


def test_composite_dict_key_token_factory_uses_stable_scalar_tuple():
    token_factory = make_token_factory(key=("tenant", "id"), normalizer=None)

    assert token_factory({"tenant": "acme", "id": 42}) == ("acme", 42)
