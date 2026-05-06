from io import BytesIO

import pytest

from uniqdiff.exceptions import TempStorageError
from uniqdiff.storage.codec import from_blob, read_record, to_blob, write_record


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        True,
        0,
        -42,
        10**30,
        1.25,
        "hello",
        "text value",
        b"bytes",
        {"id": 1, "items": ["a", "b"]},
    ],
)
def test_temp_blob_codec_round_trips_values(value):
    assert from_blob(to_blob(value)) == value


def test_temp_binary_records_round_trip():
    file = BytesIO()

    write_record(file, b"token-1", 0, b"payload-1")
    write_record(file, b"token-2", 7, b"payload-2")

    file.seek(0)
    assert read_record(file) == (b"token-1", 0, b"payload-1")
    assert read_record(file) == (b"token-2", 7, b"payload-2")
    assert read_record(file) is None


def test_temp_binary_records_reject_truncated_data():
    file = BytesIO(b"short")

    with pytest.raises(TempStorageError):
        read_record(file)
