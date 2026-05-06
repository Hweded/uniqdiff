"""Internal compact codecs for disk-backed storage.

The formats in this module are private temporary-storage details. They are not
part of the public result schema or backward compatibility contract.
"""

from __future__ import annotations

import pickle
import struct
from typing import Any, BinaryIO, Optional, cast

from uniqdiff.exceptions import TempStorageError

_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

_NONE_TAG = b"n"
_FALSE_TAG = b"b0"
_TRUE_TAG = b"b1"
_INT_TAG = b"i"
_FLOAT_TAG = b"f"
_STR_TAG = b"s"
_BYTES_TAG = b"y"
_PICKLE_TAG = b"p"

_FLOAT = struct.Struct(">d")
_RECORD_HEADER = struct.Struct(">QQQ")


def to_blob(value: Any) -> bytes:
    """Encode common scalar values compactly, falling back to pickle."""

    value_type = type(value)
    if value is None:
        return _NONE_TAG
    if value_type is bool:
        return _TRUE_TAG if value else _FALSE_TAG
    if value_type is int:
        return _INT_TAG + str(value).encode("ascii")
    if value_type is float:
        return _FLOAT_TAG + _FLOAT.pack(value)
    if value_type is str:
        return _STR_TAG + cast(str, value).encode("utf-8")
    if value_type is bytes:
        return _BYTES_TAG + cast(bytes, value)
    return _PICKLE_TAG + pickle.dumps(value, protocol=_PICKLE_PROTOCOL)


def from_blob(blob: bytes) -> Any:
    """Decode values written by :func:`to_blob`."""

    if blob == _NONE_TAG:
        return None
    if blob == _FALSE_TAG:
        return False
    if blob == _TRUE_TAG:
        return True

    tag = blob[:1]
    payload = blob[1:]
    if tag == _INT_TAG:
        return int(payload.decode("ascii"))
    if tag == _FLOAT_TAG:
        return _FLOAT.unpack(payload)[0]
    if tag == _STR_TAG:
        return payload.decode("utf-8")
    if tag == _BYTES_TAG:
        return payload
    if tag == _PICKLE_TAG:
        return pickle.loads(payload)
    raise TempStorageError("Cannot decode temporary storage blob")


def write_record(file: BinaryIO, token: bytes, ordinal: int, payload: bytes) -> None:
    """Write one temporary binary record."""

    file.write(_RECORD_HEADER.pack(len(token), ordinal, len(payload)))
    file.write(token)
    file.write(payload)


def read_record(file: BinaryIO) -> Optional[tuple[bytes, int, bytes]]:
    """Read one temporary binary record, or return None at EOF."""

    header = file.read(_RECORD_HEADER.size)
    if not header:
        return None
    if len(header) != _RECORD_HEADER.size:
        raise TempStorageError("Temporary storage record is truncated")

    token_size, ordinal, payload_size = _RECORD_HEADER.unpack(header)
    token = file.read(token_size)
    payload = file.read(payload_size)
    if len(token) != token_size or len(payload) != payload_size:
        raise TempStorageError("Temporary storage record payload is truncated")
    return token, ordinal, payload
