from dataclasses import dataclass

import pytest

from uniqdiff import KeyExtractionError, NormalizationError
from uniqdiff.tokens import make_token_factory


def test_token_factory_extracts_dict_key():
    token = make_token_factory(key="id", normalizer=None)

    assert token({"id": 1, "name": "Ann"}) == 1


def test_token_factory_extracts_object_attribute():
    @dataclass
    class User:
        id: int
        name: str

    token = make_token_factory(key="id", normalizer=None)

    assert token(User(1, "Ann")) == 1


def test_token_factory_extracts_multiple_keys():
    token = make_token_factory(key=("country", "id"), normalizer=None)

    assert token({"country": "US", "id": 1}) == ("US", 1)


def test_token_factory_applies_normalizer():
    token = make_token_factory(key="name", normalizer=lambda value: value.strip().lower())

    assert token({"name": " Alice "}) == "alice"


def test_token_factory_reports_normalizer_errors():
    def broken_normalizer(value):
        raise RuntimeError("boom")

    token = make_token_factory(key="name", normalizer=broken_normalizer)

    with pytest.raises(NormalizationError):
        token({"name": "Alice"})


def test_token_factory_reports_invalid_key_type():
    token = make_token_factory(key=object(), normalizer=None)

    with pytest.raises(KeyExtractionError):
        token({"id": 1})
