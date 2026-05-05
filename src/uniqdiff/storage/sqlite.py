"""SQLite-backed exact comparison backend."""

from __future__ import annotations

import os
import pickle
import sqlite3
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff._utils import parse_size
from uniqdiff.exceptions import DiskLimitExceededError, TempStorageError
from uniqdiff.output import StreamingResultWriter
from uniqdiff.result import CompareResult, CompareStats

TokenFactory = Callable[[Any], Any]


def compare_sqlite(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    token_factory: TokenFactory,
    include_common: bool,
    include_duplicates: bool,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]],
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
    output: Optional[str] = None,
    result_mode: str = "memory",
) -> CompareResult:
    """Compare two iterables using a temporary SQLite database."""

    db_path = _make_temp_db_path(temp_dir)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(db_path))
        _configure(conn)
        _create_schema(conn)

        first_count = _insert_items(
            conn,
            "first_items",
            first,
            token_factory=token_factory,
            chunk_size=chunk_size,
            db_path=db_path,
            disk_limit=disk_limit,
        )
        second_count = _insert_items(
            conn,
            "second_items",
            second,
            token_factory=token_factory,
            chunk_size=chunk_size,
            db_path=db_path,
            disk_limit=disk_limit,
        )
        _create_indexes(conn)

        only_in_first = _fetch_section(
            conn,
            table="first_items",
            other_table="second_items",
            relation="missing",
        )
        only_in_second = _fetch_section(
            conn,
            table="second_items",
            other_table="first_items",
            relation="missing",
        )
        common = (
            _fetch_section(
                conn,
                table="first_items",
                other_table="second_items",
                relation="present",
            )
            if include_common
            else None
        )
        duplicates_first = _fetch_duplicates(conn, "first_items") if include_duplicates else None
        duplicates_second = _fetch_duplicates(conn, "second_items") if include_duplicates else None

        unique_first_count = _count_unique(conn, "first_items")
        unique_second_count = _count_unique(conn, "second_items")
        common_count = _count_common(conn)

        if result_mode == "file":
            return _write_file_result(
                conn,
                output=output,
                include_common=include_common,
                include_duplicates=include_duplicates,
                first_count=first_count,
                second_count=second_count,
                unique_first_count=unique_first_count,
                unique_second_count=unique_second_count,
                common_count=common_count,
                mode=mode,
                strategy=strategy,
                metadata=metadata,
            )

        stats = CompareStats(
            first_count=first_count,
            second_count=second_count,
            unique_first_count=unique_first_count,
            unique_second_count=unique_second_count,
            only_in_first_count=len(only_in_first),
            only_in_second_count=len(only_in_second),
            common_count=common_count,
            duplicate_first_count=0 if duplicates_first is None else len(duplicates_first),
            duplicate_second_count=0 if duplicates_second is None else len(duplicates_second),
            mode=mode,
            strategy=strategy,
        )

        return CompareResult(
            only_in_first=only_in_first,
            only_in_second=only_in_second,
            common=common,
            unique=[*only_in_first, *only_in_second],
            duplicates_first=duplicates_first,
            duplicates_second=duplicates_second,
            stats=stats,
            metadata={**metadata, "backend": "sqlite", "temp_db_removed": True},
            warnings=[],
        )
    finally:
        if conn is not None:
            conn.close()
        db_path.unlink(missing_ok=True)


def _write_file_result(
    conn: sqlite3.Connection,
    *,
    output: Optional[str],
    include_common: bool,
    include_duplicates: bool,
    first_count: int,
    second_count: int,
    unique_first_count: int,
    unique_second_count: int,
    common_count: int,
    mode: str,
    strategy: str,
    metadata: dict[str, Any],
) -> CompareResult:
    if output is None:
        raise TempStorageError("result_mode='file' requires output")

    only_in_first_count = 0
    only_in_second_count = 0
    duplicate_first_count = 0
    duplicate_second_count = 0
    with StreamingResultWriter(output) as writer:
        for value in _iter_section(
            conn,
            table="first_items",
            other_table="second_items",
            relation="missing",
        ):
            writer.write("only_in_first", value)
            only_in_first_count += 1
        for value in _iter_section(
            conn,
            table="second_items",
            other_table="first_items",
            relation="missing",
        ):
            writer.write("only_in_second", value)
            only_in_second_count += 1
        if include_common:
            for value in _iter_section(
                conn,
                table="first_items",
                other_table="second_items",
                relation="present",
            ):
                writer.write("common", value)
        if include_duplicates:
            for value in _iter_duplicates(conn, "first_items"):
                writer.write("duplicates_first", value)
                duplicate_first_count += 1
            for value in _iter_duplicates(conn, "second_items"):
                writer.write("duplicates_second", value)
                duplicate_second_count += 1

    return CompareResult(
        stats=CompareStats(
            first_count=first_count,
            second_count=second_count,
            unique_first_count=unique_first_count,
            unique_second_count=unique_second_count,
            only_in_first_count=only_in_first_count,
            only_in_second_count=only_in_second_count,
            common_count=common_count,
            duplicate_first_count=duplicate_first_count,
            duplicate_second_count=duplicate_second_count,
            mode=mode,
            strategy=strategy,
        ),
        metadata={
            **metadata,
            "backend": "sqlite",
            "output": output,
            "result_mode": "file",
            "temp_db_removed": True,
        },
        warnings=["Result rows were streamed to output and are not materialized in memory."],
    )


def duplicates_sqlite(
    data: Iterable[Any],
    *,
    token_factory: TokenFactory,
    chunk_size: int,
    temp_dir: Optional[str],
    disk_limit: Optional[Union[str, int]] = None,
) -> list[Any]:
    """Return duplicate items using a temporary SQLite database."""

    db_path = _make_temp_db_path(temp_dir)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(db_path))
        _configure(conn)
        conn.execute(
            "CREATE TABLE first_items "
            "(token BLOB NOT NULL, ordinal INTEGER NOT NULL, payload BLOB NOT NULL)"
        )
        _insert_items(
            conn,
            "first_items",
            data,
            token_factory=token_factory,
            chunk_size=chunk_size,
            db_path=db_path,
            disk_limit=disk_limit,
        )
        conn.execute("CREATE INDEX idx_first_token ON first_items(token)")
        return _fetch_duplicates(conn, "first_items")
    finally:
        if conn is not None:
            conn.close()
        db_path.unlink(missing_ok=True)


def _make_temp_db_path(temp_dir: Optional[str]) -> Path:
    base_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="uniqdiff-", suffix=".sqlite3", dir=str(base_dir))
        os.close(fd)
    except OSError as exc:
        raise TempStorageError(f"Cannot create temporary SQLite storage in {base_dir!s}") from exc
    return Path(name)


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = FILE")


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE first_items "
        "(token BLOB NOT NULL, ordinal INTEGER NOT NULL, payload BLOB NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE second_items "
        "(token BLOB NOT NULL, ordinal INTEGER NOT NULL, payload BLOB NOT NULL)"
    )


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX idx_first_token ON first_items(token)")
    conn.execute("CREATE INDEX idx_second_token ON second_items(token)")


def _insert_items(
    conn: sqlite3.Connection,
    table: str,
    items: Iterable[Any],
    *,
    token_factory: TokenFactory,
    chunk_size: int,
    db_path: Path,
    disk_limit: Optional[Union[str, int]],
) -> int:
    count = 0
    batch: list[tuple[bytes, int, bytes]] = []
    committed = False
    conn.execute("BEGIN")
    try:
        for item in items:
            batch.append((_to_blob(token_factory(item)), count, _to_blob(item)))
            count += 1
            if len(batch) >= chunk_size:
                _insert_batch(conn, table, batch)
                _check_disk_limit(db_path, disk_limit)
                batch.clear()

        if batch:
            _insert_batch(conn, table, batch)
            _check_disk_limit(db_path, disk_limit)
        conn.commit()
        committed = True
        return count
    finally:
        if not committed:
            conn.rollback()


def _insert_batch(
    conn: sqlite3.Connection,
    table: str,
    batch: list[tuple[bytes, int, bytes]],
) -> None:
    conn.executemany(
        f"INSERT INTO {table} (token, ordinal, payload) VALUES (?, ?, ?)",
        batch,
    )


def _fetch_section(
    conn: sqlite3.Connection,
    *,
    table: str,
    other_table: str,
    relation: str,
) -> list[Any]:
    comparator = "EXISTS" if relation == "present" else "NOT EXISTS"
    cursor = conn.execute(
        f"""
        SELECT item.payload
        FROM {table} AS item
        JOIN (
            SELECT token, MIN(ordinal) AS first_ordinal
            FROM {table}
            GROUP BY token
        ) AS first_seen
          ON item.token = first_seen.token
         AND item.ordinal = first_seen.first_ordinal
        WHERE {comparator} (
            SELECT 1 FROM {other_table} AS other WHERE other.token = item.token
        )
        ORDER BY item.ordinal
        """
    )
    return [_from_blob(row[0]) for row in cursor.fetchall()]


def _iter_section(
    conn: sqlite3.Connection,
    *,
    table: str,
    other_table: str,
    relation: str,
) -> Iterable[Any]:
    comparator = "EXISTS" if relation == "present" else "NOT EXISTS"
    cursor = conn.execute(
        f"""
        SELECT item.payload
        FROM {table} AS item
        JOIN (
            SELECT token, MIN(ordinal) AS first_ordinal
            FROM {table}
            GROUP BY token
        ) AS first_seen
          ON item.token = first_seen.token
         AND item.ordinal = first_seen.first_ordinal
        WHERE {comparator} (
            SELECT 1 FROM {other_table} AS other WHERE other.token = item.token
        )
        ORDER BY item.ordinal
        """
    )
    for row in cursor:
        yield _from_blob(row[0])


def _fetch_duplicates(conn: sqlite3.Connection, table: str) -> list[Any]:
    cursor = conn.execute(
        f"""
        SELECT item.payload
        FROM {table} AS item
        WHERE item.rowid NOT IN (
            SELECT MIN(rowid)
            FROM {table}
            GROUP BY token
        )
        ORDER BY item.ordinal
        """
    )
    return [_from_blob(row[0]) for row in cursor.fetchall()]


def _iter_duplicates(conn: sqlite3.Connection, table: str) -> Iterable[Any]:
    cursor = conn.execute(
        f"""
        SELECT item.payload
        FROM {table} AS item
        WHERE item.rowid NOT IN (
            SELECT MIN(rowid)
            FROM {table}
            GROUP BY token
        )
        ORDER BY item.ordinal
        """
    )
    for row in cursor:
        yield _from_blob(row[0])


def _count_unique(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM (SELECT token FROM {table} GROUP BY token)"
    ).fetchone()
    return int(row[0])


def _count_common(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT token FROM first_items GROUP BY token
            INTERSECT
            SELECT token FROM second_items GROUP BY token
        )
        """
    ).fetchone()
    return int(row[0])


def _to_blob(value: Any) -> bytes:
    return pickle.dumps(value, protocol=4)


def _from_blob(value: bytes) -> Any:
    return pickle.loads(value)


def _check_disk_limit(db_path: Path, disk_limit: Optional[Union[str, int]]) -> None:
    if disk_limit is None:
        return
    limit = parse_size(disk_limit)
    if db_path.stat().st_size > limit:
        raise DiskLimitExceededError(
            f"Temporary SQLite storage exceeded disk_limit={disk_limit!r}"
        )
