"""Command line interface for uniqdiff."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff import (
    FieldDiffResult,
    SchemaDiffResult,
    compare_file_fields,
    compare_file_fields_sorted,
    compare_file_schema,
    compare_files,
    duplicates,
    iter_field_diff_sorted,
)
from uniqdiff.disk import atomic_write_result
from uniqdiff.exceptions import UniqDiffError
from uniqdiff.io.readers import read_file
from uniqdiff.normalizers import string_normalizer
from uniqdiff.output import (
    JsonlWriter,
    build_metadata_event,
    build_summary_event,
    compare_result_events,
    event_key,
    iter_result_rows,
    validate_event,
)
from uniqdiff.result import CompareResult


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the uniqdiff CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
        if _wants_jsonl_events(args):
            _run_jsonl_event_command(args)
            return 0
        payload = _run_command(args)
    except (OSError, UniqDiffError, ValueError) as exc:
        print(_format_error(exc), file=sys.stderr)
        return 2

    if isinstance(payload, CompareResult):
        return _handle_compare_result(payload, args)
    if isinstance(payload, FieldDiffResult):
        return _handle_field_diff_result(payload, args)
    if isinstance(payload, SchemaDiffResult):
        return _handle_schema_diff_result(payload, args)
    return _handle_list_result(payload, args)


def _handle_compare_result(result: CompareResult, args: argparse.Namespace) -> int:
    if args.summary:
        _write_stdout(_summary_payload(result))
        return _exit_code(result, args)
    if result.metadata.get("result_mode") == "file":
        return _exit_code(result, args)
    if args.output:
        atomic_write_result(result, args.output)
    else:
        _write_stdout(result.to_dict())
    return _exit_code(result, args)


def _handle_field_diff_result(result: FieldDiffResult, args: argparse.Namespace) -> int:
    if args.summary:
        _write_stdout(_field_summary_payload(result))
        return _exit_code(result, args)
    if result.metadata.get("result_mode") == "file":
        return _exit_code(result, args)
    if args.output:
        _atomic_write_json(result.to_dict(), args.output)
    else:
        _write_stdout(result.to_dict())
    return _exit_code(result, args)


def _handle_schema_diff_result(result: SchemaDiffResult, args: argparse.Namespace) -> int:
    payload = _schema_summary_payload(result) if args.summary else result.to_dict()
    if args.output:
        _atomic_write_json(payload, args.output)
    else:
        _write_stdout(payload)
    return _exit_code(result, args)


def _handle_list_result(payload: list[Any], args: argparse.Namespace) -> int:
    output_payload: Union[list[Any], dict[str, Any]]
    output_payload = _list_summary_payload(payload, args.command) if args.summary else payload
    output = getattr(args, "output", None)
    if output:
        _atomic_write_json(output_payload, output)
    else:
        _write_stdout(output_payload)
    return _exit_code(output_payload, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uniqdiff",
        description="Compare files and return unique differences.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("compare", "diff", "intersection"):
        command = subparsers.add_parser(name, help=f"{name} two files")
        _add_input_file_args(command, two_files=True)
        _add_backend_args(command, include_memory_limit=True)
        _add_output_args(command)
        _add_common_behavior_args(command)
        command.add_argument(
            "--include-duplicates",
            action="store_true",
            help="Include duplicates from both inputs in compare results.",
        )
        if name in {"compare", "diff"}:
            _add_field_diff_args(command)
            _add_schema_diff_args(command)

    duplicates_command = subparsers.add_parser("duplicates", help="Find duplicates in one file")
    _add_input_file_args(duplicates_command, two_files=False)
    _add_backend_args(duplicates_command, include_memory_limit=False)
    _add_common_behavior_args(duplicates_command)

    return parser


def _add_input_file_args(parser: argparse.ArgumentParser, *, two_files: bool) -> None:
    parser.add_argument("file_a", help="First input file.")
    if two_files:
        parser.add_argument("file_b", help="Second input file.")
    parser.add_argument(
        "--format",
        default="auto",
        help=(
            "Input format: auto, csv, tsv, jsonl, parquet, txt. For compare/diff, "
            "jsonl can also request uniqdiff.jsonl event output when input is inferred."
        ),
    )
    parser.add_argument(
        "--input-format",
        choices=["auto", "csv", "tsv", "jsonl", "parquet", "txt"],
        help="Explicit input format when --format is used for output.",
    )
    parser.add_argument("--encoding", default="utf-8", help="Input file encoding.")
    parser.add_argument("--key", help="Dictionary/object key. Use comma for composite keys.")
    parser.add_argument("--delimiter", help="CSV/TSV delimiter override.")
    parser.add_argument("--quotechar", default='"', help="CSV/TSV quote character.")
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Read CSV/TSV files without a header row.",
    )
    parser.add_argument(
        "--fieldnames",
        help="Comma-separated field names for CSV/TSV files without a header row.",
    )
    parser.add_argument(
        "--columns",
        help="Comma-separated columns to read from Parquet files.",
    )
    parser.add_argument(
        "--parquet-batch-size",
        type=int,
        default=65_536,
        help="Rows per Parquet batch.",
    )


def _add_backend_args(parser: argparse.ArgumentParser, *, include_memory_limit: bool) -> None:
    parser.add_argument("--mode", default="memory", choices=["memory", "disk", "auto"])
    parser.add_argument("--chunk-size", type=int, default=100_000)
    if include_memory_limit:
        parser.add_argument("--memory-limit")
    parser.add_argument("--temp-dir")
    parser.add_argument("--disk-limit")
    parser.add_argument(
        "--disk-strategy",
        default="sqlite",
        choices=["sqlite", "hash-partition", "hash_partition", "external-sort", "external_sort"],
        help="Disk backend to use with --mode disk.",
    )
    parser.add_argument("--partition-count", type=int, help="Number of hash partitions.")


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--result-mode",
        default="memory",
        choices=["memory", "file"],
        help="Materialize result in memory or stream it to --output.",
    )
    parser.add_argument(
        "--output",
        help="Output file. Supports .json, .jsonl, .csv for comparisons.",
    )


def _add_field_diff_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--field-diff",
        action="store_true",
        help="Compare changed fields for rows with the same --key.",
    )
    parser.add_argument(
        "--exclude-columns",
        help="Comma-separated columns to ignore in --field-diff.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Maximum changed rows to emit for --field-diff.",
    )
    parser.add_argument(
        "--max-bytes",
        help="Maximum JSONL bytes to write for streaming --field-diff output.",
    )
    parser.add_argument(
        "--sorted-input",
        action="store_true",
        help=("Use low-memory streaming field diff. Both inputs must already be sorted by --key."),
    )


def _add_schema_diff_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--schema-diff",
        action="store_true",
        help="Compare inferred columns, types, and nullability.",
    )
    parser.add_argument(
        "--schema-sample-size",
        type=int,
        help="Maximum rows per input to inspect for --schema-diff.",
    )
    parser.add_argument(
        "--empty-string-not-null",
        action="store_true",
        help="Treat empty strings as strings instead of nulls in --schema-diff.",
    )
    parser.add_argument(
        "--loose-numeric-types",
        action="store_true",
        help="Treat int and float as a shared number type in --schema-diff.",
    )


def _add_common_behavior_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact JSON counters instead of full result rows.",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help=(
            "Return exit code 1 when compare/diff find differences or duplicates finds duplicates."
        ),
    )
    parser.add_argument("--lower", action="store_true", help="Lowercase values before comparison.")
    parser.add_argument(
        "--strip",
        action="store_true",
        default=True,
        help="Strip values before comparison.",
    )
    parser.add_argument(
        "--no-strip",
        action="store_false",
        dest="strip",
        help="Do not strip values.",
    )
    parser.add_argument(
        "--remove-spaces",
        action="store_true",
        help="Remove whitespace before comparison.",
    )
    parser.add_argument(
        "--remove-special",
        action="store_true",
        help="Remove special chars before comparison.",
    )


def _run_command(
    args: argparse.Namespace,
) -> Union[CompareResult, FieldDiffResult, SchemaDiffResult, list[Any]]:
    key = _parse_key(args.key)
    normalizer = _build_normalizer(args)
    fieldnames = _parse_fieldnames(args.fieldnames)
    columns = _parse_fieldnames(args.columns)

    if args.command == "duplicates":
        return duplicates(
            read_file(
                args.file_a,
                format=_input_format(args),
                encoding=args.encoding,
                delimiter=args.delimiter,
                quotechar=args.quotechar,
                has_header=not args.no_header,
                fieldnames=fieldnames,
                columns=columns,
                batch_size=args.parquet_batch_size,
            ),
            key=key,
            normalizer=normalizer,
            mode=args.mode,
            chunk_size=args.chunk_size,
            temp_dir=args.temp_dir,
            disk_limit=args.disk_limit,
            disk_strategy=args.disk_strategy,
            partition_count=args.partition_count,
        )

    if getattr(args, "schema_diff", False):
        if getattr(args, "field_diff", False):
            raise ValueError("--schema-diff cannot be combined with --field-diff")
        return compare_file_schema(
            args.file_a,
            args.file_b,
            format=_input_format(args),
            encoding=args.encoding,
            delimiter=args.delimiter,
            quotechar=args.quotechar,
            has_header=not args.no_header,
            fieldnames=fieldnames,
            columns=columns,
            batch_size=args.parquet_batch_size,
            sample_size=args.schema_sample_size,
            empty_string_null=not args.empty_string_not_null,
            strict_numeric_types=not args.loose_numeric_types,
        )

    if getattr(args, "field_diff", False):
        if key is None:
            raise ValueError("--field-diff requires --key")
        if getattr(args, "sorted_input", False):
            return _run_sorted_field_diff(
                args,
                key=key,
                normalizer=normalizer,
                fieldnames=fieldnames,
                columns=columns,
            )
        return compare_file_fields(
            args.file_a,
            args.file_b,
            format=_input_format(args),
            encoding=args.encoding,
            delimiter=args.delimiter,
            quotechar=args.quotechar,
            has_header=not args.no_header,
            fieldnames=fieldnames,
            columns=columns,
            batch_size=args.parquet_batch_size,
            key=key,
            normalizer=normalizer,
            output=args.output,
            max_rows=args.max_rows,
            max_bytes=args.max_bytes,
            exclude_columns=_parse_fieldnames(args.exclude_columns),
        )

    include_common = args.command in {"compare", "intersection"}
    result = compare_files(
        args.file_a,
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=fieldnames,
        columns=columns,
        batch_size=args.parquet_batch_size,
        key=key,
        normalizer=normalizer,
        mode=args.mode,
        include_common=include_common,
        include_duplicates=args.include_duplicates,
        chunk_size=args.chunk_size,
        memory_limit=getattr(args, "memory_limit", None),
        temp_dir=args.temp_dir,
        disk_limit=args.disk_limit,
        disk_strategy=args.disk_strategy,
        partition_count=args.partition_count,
        output=args.output,
        result_mode=args.result_mode,
    )

    if args.command == "intersection":
        return result.common or []

    return result


def _validate_args(args: argparse.Namespace) -> None:
    command = getattr(args, "command", None)
    if command not in {"compare", "diff", "intersection"}:
        return

    field_diff = bool(getattr(args, "field_diff", False))
    schema_diff = bool(getattr(args, "schema_diff", False))
    output = getattr(args, "output", None)
    result_mode = getattr(args, "result_mode", "memory")
    event_stream = _wants_jsonl_events(args)

    if field_diff and schema_diff:
        raise ValueError("--schema-diff cannot be combined with --field-diff")
    if getattr(args, "sorted_input", False) and not field_diff:
        raise ValueError("--sorted-input requires --field-diff")
    if schema_diff and command == "intersection":
        raise ValueError("--schema-diff is supported only for compare and diff")
    if field_diff and command == "intersection":
        raise ValueError("--field-diff is supported only for compare and diff")
    if field_diff and not getattr(args, "key", None):
        raise ValueError("--field-diff requires --key")

    if (field_diff or schema_diff) and result_mode != "memory":
        raise ValueError("--result-mode is not used with --field-diff or --schema-diff")
    if event_stream and output is not None and Path(output).suffix.lower() != ".jsonl":
        raise ValueError("--format jsonl --output supports only .jsonl")
    if (
        schema_diff
        and not event_stream
        and output is not None
        and Path(output).suffix.lower() != ".json"
    ):
        raise ValueError("--schema-diff --output supports only .json")
    if field_diff and output is not None and Path(output).suffix.lower() != ".jsonl":
        raise ValueError("--field-diff --output supports only .jsonl")


def _run_jsonl_event_command(args: argparse.Namespace) -> None:
    def produce(writer: JsonlWriter) -> None:
        if getattr(args, "schema_diff", False):
            _write_schema_diff_events(args, writer)
        elif getattr(args, "field_diff", False):
            _write_field_diff_events(args, writer)
        else:
            _write_compare_events(args, writer)

    _write_event_output(args, produce)


def _write_event_output(
    args: argparse.Namespace,
    producer: Callable[[JsonlWriter], None],
) -> None:
    output = getattr(args, "output", None)
    if output is None:
        producer(JsonlWriter(sys.stdout))
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=str(output_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as file:
            producer(JsonlWriter(file))
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _write_compare_events(args: argparse.Namespace, writer: JsonlWriter) -> None:
    key = _parse_key(args.key)
    normalizer = _build_normalizer(args)
    columns = _parse_fieldnames(args.columns)
    read_columns = _columns_with_key(columns, key)
    metadata = build_metadata_event(
        mode=args.command,
        key_columns=_key_columns(key),
        compared_columns=columns,
    )
    writer.write_event(metadata)

    if args.mode != "memory" or args.result_mode == "file":
        output = _temporary_jsonl_path(args)
        try:
            result = compare_files(
                args.file_a,
                args.file_b,
                format=_input_format(args),
                encoding=args.encoding,
                delimiter=args.delimiter,
                quotechar=args.quotechar,
                has_header=not args.no_header,
                fieldnames=_parse_fieldnames(args.fieldnames),
                columns=read_columns,
                batch_size=args.parquet_batch_size,
                key=key,
                normalizer=normalizer,
                mode=args.mode,
                include_common=args.command == "compare",
                include_duplicates=args.include_duplicates,
                chunk_size=args.chunk_size,
                memory_limit=getattr(args, "memory_limit", None),
                temp_dir=args.temp_dir,
                disk_limit=args.disk_limit,
                disk_strategy=args.disk_strategy,
                partition_count=args.partition_count,
                output=str(output),
                result_mode="file",
            )
            _write_legacy_result_events(output, writer, key=key)
        finally:
            output.unlink(missing_ok=True)
        writer.write_event(_compare_summary_event(result))
        return

    result = compare_files(
        args.file_a,
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=_parse_fieldnames(args.fieldnames),
        columns=read_columns,
        batch_size=args.parquet_batch_size,
        key=key,
        normalizer=normalizer,
        mode=args.mode,
        include_common=args.command == "compare",
        include_duplicates=args.include_duplicates,
        chunk_size=args.chunk_size,
        memory_limit=getattr(args, "memory_limit", None),
        temp_dir=args.temp_dir,
        disk_limit=args.disk_limit,
        disk_strategy=args.disk_strategy,
        partition_count=args.partition_count,
        result_mode="memory",
    )
    events = compare_result_events(
        result,
        key=key,
        mode=args.command,
        compared_columns=columns,
    )
    next(events, None)
    for event in events:
        writer.write_event(event)


def _write_legacy_result_events(
    output: Path,
    writer: JsonlWriter,
    *,
    key: Optional[Union[str, tuple[str, ...]]],
) -> None:
    duplicate_counts: dict[tuple[tuple[str, Any], ...], int] = {}
    duplicate_keys: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}
    duplicate_sides: dict[tuple[tuple[str, Any], ...], str] = {}

    for row in iter_result_rows(output):
        section = row["section"]
        value = row["value"]
        if section == "only_in_first":
            writer.write_event({"type": "only_left", "key": event_key(value, key=key)})
        elif section == "only_in_second":
            writer.write_event({"type": "only_right", "key": event_key(value, key=key)})
        elif section in {"duplicates_first", "duplicates_second"}:
            side = "left" if section == "duplicates_first" else "right"
            key_value = event_key(value, key=key)
            stable_key = tuple(sorted(key_value.items()))
            duplicate_counts[stable_key] = duplicate_counts.get(stable_key, 0) + 1
            duplicate_keys[stable_key] = key_value
            duplicate_sides[stable_key] = side

    for stable_key, count in duplicate_counts.items():
        writer.write_event(
            {
                "type": "duplicate_key",
                "side": duplicate_sides[stable_key],
                "key": duplicate_keys[stable_key],
                "count": count + 1,
            }
        )


def _compare_summary_event(result: CompareResult) -> dict[str, Any]:
    stats = result.stats
    return build_summary_event(
        left_rows=stats.first_count,
        right_rows=stats.second_count,
        common_rows=stats.common_count,
        only_left=stats.only_in_first_count,
        only_right=stats.only_in_second_count,
        duplicate_keys_left=stats.duplicate_first_count,
        duplicate_keys_right=stats.duplicate_second_count,
    )


def _write_field_diff_events(args: argparse.Namespace, writer: JsonlWriter) -> None:
    key = _parse_key(args.key)
    if key is None:
        raise ValueError("--field-diff requires --key")
    columns = _parse_fieldnames(args.columns)
    read_columns = _columns_with_key(columns, key)
    compared_columns = _compared_columns(
        columns=columns,
        exclude_columns=_parse_fieldnames(args.exclude_columns),
    )
    writer.write_event(
        build_metadata_event(
            mode="field_diff",
            key_columns=_key_columns(key),
            compared_columns=compared_columns,
        )
    )

    if getattr(args, "sorted_input", False):
        _write_sorted_field_diff_events(
            args,
            writer,
            key=key,
        )
        return

    presence = compare_files(
        args.file_a,
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=_parse_fieldnames(args.fieldnames),
        columns=read_columns,
        batch_size=args.parquet_batch_size,
        key=key,
        normalizer=_build_normalizer(args),
        mode=args.mode,
        include_common=False,
        include_duplicates=args.include_duplicates,
        chunk_size=args.chunk_size,
        memory_limit=getattr(args, "memory_limit", None),
        temp_dir=args.temp_dir,
        disk_limit=args.disk_limit,
        disk_strategy=args.disk_strategy,
        partition_count=args.partition_count,
        result_mode="memory",
    )
    for row in presence.only_in_first:
        writer.write_event({"type": "only_left", "key": event_key(row, key=key)})
    for row in presence.only_in_second:
        writer.write_event({"type": "only_right", "key": event_key(row, key=key)})

    field_output = _temporary_jsonl_path(args)
    try:
        field_result = compare_file_fields(
            args.file_a,
            args.file_b,
            format=_input_format(args),
            encoding=args.encoding,
            delimiter=args.delimiter,
            quotechar=args.quotechar,
            has_header=not args.no_header,
            fieldnames=_parse_fieldnames(args.fieldnames),
            columns=columns,
            batch_size=args.parquet_batch_size,
            key=key,
            normalizer=_build_normalizer(args),
            output=str(field_output),
            max_rows=args.max_rows,
            max_bytes=args.max_bytes,
            exclude_columns=_parse_fieldnames(args.exclude_columns),
        )
        for row in _iter_field_event_rows(field_output, key_columns=_key_columns(key)):
            writer.write_event(row)
    finally:
        field_output.unlink(missing_ok=True)

    writer.write_event(
        build_summary_event(
            left_rows=presence.stats.first_count,
            right_rows=presence.stats.second_count,
            common_rows=presence.stats.common_count,
            only_left=presence.stats.only_in_first_count,
            only_right=presence.stats.only_in_second_count,
            changed_rows=field_result.stats.changed_row_count,
            changed_fields=field_result.stats.changed_field_count,
            duplicate_keys_left=presence.stats.duplicate_first_count,
            duplicate_keys_right=presence.stats.duplicate_second_count,
        )
    )


def _run_sorted_field_diff(
    args: argparse.Namespace,
    *,
    key: Union[str, tuple[str, ...]],
    normalizer: Optional[Any],
    fieldnames: Optional[Sequence[str]],
    columns: Optional[Sequence[str]],
) -> FieldDiffResult:
    return compare_file_fields_sorted(
        args.file_a,
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=fieldnames,
        columns=columns,
        batch_size=args.parquet_batch_size,
        key=key,
        normalizer=normalizer,
        output=args.output,
        max_rows=args.max_rows,
        max_bytes=args.max_bytes,
        exclude_columns=_parse_fieldnames(args.exclude_columns),
    )


def _sorted_field_diff_rows(
    args: argparse.Namespace,
    *,
    key: Union[str, tuple[str, ...]],
    normalizer: Optional[Any],
    fieldnames: Optional[Sequence[str]],
    columns: Optional[Sequence[str]],
) -> Iterator[dict[str, Any]]:
    read_columns = _columns_with_key(columns, key)
    first = read_file(
        args.file_a,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=args.parquet_batch_size,
    )
    second = read_file(
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=fieldnames,
        columns=read_columns,
        batch_size=args.parquet_batch_size,
    )
    return iter_field_diff_sorted(
        first,
        second,
        key=key,
        columns=columns,
        exclude_columns=_parse_fieldnames(args.exclude_columns),
        normalizer=normalizer,
    )


def _write_sorted_field_diff_events(
    args: argparse.Namespace,
    writer: JsonlWriter,
    *,
    key: Union[str, tuple[str, ...]],
) -> None:
    rows = _sorted_field_diff_rows(
        args,
        key=key,
        normalizer=_build_normalizer(args),
        fieldnames=_parse_fieldnames(args.fieldnames),
        columns=_parse_fieldnames(args.columns),
    )
    changed_rows = 0
    changed_fields = 0
    emitted_rows = 0

    for row in rows:
        changed_rows += 1
        changes = list(row.get("changes", ()))
        changed_fields += len(changes)
        if args.max_rows is not None and emitted_rows >= args.max_rows:
            continue
        for event in _iter_memory_field_event_rows([row], key_columns=_key_columns(key)):
            writer.write_event(event)
        emitted_rows += 1

    writer.write_event(
        build_summary_event(
            changed_rows=changed_rows,
            changed_fields=changed_fields,
        )
    )


def _write_schema_diff_events(args: argparse.Namespace, writer: JsonlWriter) -> None:
    writer.write_event(build_metadata_event(mode="schema_diff"))
    result = compare_file_schema(
        args.file_a,
        args.file_b,
        format=_input_format(args),
        encoding=args.encoding,
        delimiter=args.delimiter,
        quotechar=args.quotechar,
        has_header=not args.no_header,
        fieldnames=_parse_fieldnames(args.fieldnames),
        columns=_parse_fieldnames(args.columns),
        batch_size=args.parquet_batch_size,
        sample_size=args.schema_sample_size,
        empty_string_null=not args.empty_string_not_null,
        strict_numeric_types=not args.loose_numeric_types,
    )
    schema_changes = 0
    for column in result.added_columns:
        schema_changes += 1
        writer.write_event({"type": "schema_change", "change": "column_added", "column": column})
    for column in result.removed_columns:
        schema_changes += 1
        writer.write_event({"type": "schema_change", "change": "column_removed", "column": column})
    for change in result.type_changes:
        schema_changes += 1
        writer.write_event(
            {
                "type": "schema_change",
                "change": "type_changed",
                "column": change["column"],
                "left_type": _one_or_many(change["left_types"]),
                "right_type": _one_or_many(change["right_types"]),
            }
        )
    for change in result.nullable_changes:
        schema_changes += 1
        writer.write_event(
            {
                "type": "schema_change",
                "change": "nullable_changed",
                "column": change["column"],
                "left_nullable": change["left_nullable"],
                "right_nullable": change["right_nullable"],
            }
        )
    writer.write_event(
        build_summary_event(
            left_rows=result.left_schema.row_count,
            right_rows=result.right_schema.row_count,
            schema_changes=schema_changes,
        )
    )


def _iter_field_event_rows(
    output: Path,
    *,
    key_columns: Sequence[str],
) -> Iterator[dict[str, Any]]:
    with output.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            key_value = event_key(row["key"], key_columns=key_columns)
            changes = row.get("changes", ())
            changed_columns = [change["field"] for change in changes]
            if changed_columns:
                event = {
                    "type": "row_changed",
                    "key": key_value,
                    "changed_columns": changed_columns,
                }
                validate_event(event)
                yield event
            for change in changes:
                event = {
                    "type": "field_change",
                    "key": key_value,
                    "column": change["field"],
                    "left": change.get("left"),
                    "right": change.get("right"),
                }
                validate_event(event)
                yield event


def _iter_memory_field_event_rows(
    rows: Sequence[dict[str, Any]],
    *,
    key_columns: Sequence[str],
) -> Iterator[dict[str, Any]]:
    for row in rows:
        key_value = event_key(row["key"], key_columns=key_columns)
        changes = row.get("changes", ())
        changed_columns = [change["field"] for change in changes]
        if changed_columns:
            event = {
                "type": "row_changed",
                "key": key_value,
                "changed_columns": changed_columns,
            }
            validate_event(event)
            yield event
        for change in changes:
            event = {
                "type": "field_change",
                "key": key_value,
                "column": change["field"],
                "left": change.get("left"),
                "right": change.get("right"),
            }
            validate_event(event)
            yield event


def _temporary_jsonl_path(args: argparse.Namespace) -> Path:
    temp_dir = args.temp_dir if getattr(args, "temp_dir", None) else None
    fd, temp_name = tempfile.mkstemp(prefix=".uniqdiff-events.", suffix=".jsonl", dir=temp_dir)
    os.close(fd)
    return Path(temp_name)


def _wants_jsonl_events(args: argparse.Namespace) -> bool:
    if getattr(args, "command", None) not in {"compare", "diff"}:
        return False
    if getattr(args, "format", None) != "jsonl":
        return False
    if getattr(args, "input_format", None):
        return True
    files = [getattr(args, "file_a", ""), getattr(args, "file_b", "")]
    return not all(_has_jsonl_suffix(file_name) for file_name in files)


def _input_format(args: argparse.Namespace) -> str:
    explicit = getattr(args, "input_format", None)
    if explicit:
        return str(explicit)
    if _wants_jsonl_events(args):
        return "auto"
    if getattr(args, "format", None) == "json":
        return "auto"
    return str(args.format)


def _has_jsonl_suffix(value: str) -> bool:
    path = Path(value)
    suffixes = [suffix.lower() for suffix in path.suffixes]
    return suffixes[-1:] == [".jsonl"] or suffixes[-2:] == [".jsonl", ".gz"]


def _key_columns(key: Optional[Union[str, tuple[str, ...]]]) -> list[str]:
    if isinstance(key, str):
        return [key]
    if isinstance(key, tuple):
        return list(key)
    return []


def _compared_columns(
    *,
    columns: Optional[Sequence[str]],
    exclude_columns: Optional[Sequence[str]],
) -> list[str]:
    values = list(columns or ())
    excluded = set(exclude_columns or ())
    return [value for value in values if value not in excluded]


def _columns_with_key(
    columns: Optional[Sequence[str]],
    key: Optional[Union[str, tuple[str, ...]]],
) -> Optional[tuple[str, ...]]:
    if columns is None:
        return None
    values = list(columns)
    if isinstance(key, str):
        values.append(key)
    elif isinstance(key, tuple):
        values.extend(key)
    return tuple(dict.fromkeys(values))


def _one_or_many(values: Sequence[Any]) -> Any:
    return values[0] if len(values) == 1 else list(values)


def _parse_key(value: Optional[str]) -> Optional[Union[str, tuple[str, ...]]]:
    if value is None:
        return None
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return parts


def _parse_fieldnames(value: Optional[str]) -> Optional[tuple[str, ...]]:
    if value is None:
        return None
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    return parts or None


def _build_normalizer(args: argparse.Namespace) -> Optional[Any]:
    if not any((args.lower, args.remove_spaces, args.remove_special, not args.strip)):
        return None
    return string_normalizer(
        lower=args.lower,
        strip=args.strip,
        remove_spaces=args.remove_spaces,
        remove_special=args.remove_special,
    )


def _write_stdout(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _summary_payload(result: CompareResult) -> dict[str, Any]:
    stats = result.stats.to_dict()
    return {
        "equal": stats["only_in_first_count"] == 0
        and stats["only_in_second_count"] == 0
        and stats["duplicate_first_count"] == 0
        and stats["duplicate_second_count"] == 0,
        "only_in_first_count": stats["only_in_first_count"],
        "only_in_second_count": stats["only_in_second_count"],
        "common_count": stats["common_count"],
        "duplicate_first_count": stats["duplicate_first_count"],
        "duplicate_second_count": stats["duplicate_second_count"],
        "first_count": stats["first_count"],
        "second_count": stats["second_count"],
        "backend": result.metadata.get("backend"),
        "mode": stats["mode"],
        "strategy": stats["strategy"],
        "result_mode": result.metadata.get("result_mode"),
        "output": result.metadata.get("output"),
        "warnings": result.warnings,
    }


def _field_summary_payload(result: FieldDiffResult) -> dict[str, Any]:
    stats = result.stats.to_dict()
    return {
        "equal": stats["changed_row_count"] == 0,
        "changed_row_count": stats["changed_row_count"],
        "changed_field_count": stats["changed_field_count"],
        "emitted_row_count": stats["emitted_row_count"],
        "compared_count": stats["compared_count"],
        "first_count": stats["first_count"],
        "second_count": stats["second_count"],
        "summary_by_column": result.summary_by_column,
        "truncated": stats["truncated"],
        "output": result.metadata.get("output"),
        "warnings": result.warnings,
    }


def _schema_summary_payload(result: SchemaDiffResult) -> dict[str, Any]:
    return {
        "equal": not result.has_changes,
        "added_column_count": len(result.added_columns),
        "removed_column_count": len(result.removed_columns),
        "type_change_count": len(result.type_changes),
        "nullable_change_count": len(result.nullable_changes),
        "added_columns": result.added_columns,
        "removed_columns": result.removed_columns,
        "type_changes": result.type_changes,
        "nullable_changes": result.nullable_changes,
        "left_row_count": result.left_schema.row_count,
        "right_row_count": result.right_schema.row_count,
        "warnings": result.warnings,
    }


def _list_summary_payload(payload: list[Any], command: str) -> dict[str, Any]:
    count_name = "duplicate_count" if command == "duplicates" else "count"
    return {count_name: len(payload), "empty": len(payload) == 0}


def _exit_code(
    payload: Union[CompareResult, FieldDiffResult, SchemaDiffResult, list[Any], dict[str, Any]],
    args: argparse.Namespace,
) -> int:
    if not args.fail_on_diff:
        return 0
    if isinstance(payload, FieldDiffResult) and args.command in {"compare", "diff"}:
        return 1 if payload.stats.changed_row_count > 0 else 0
    if isinstance(payload, SchemaDiffResult) and args.command in {"compare", "diff"}:
        return 1 if payload.has_changes else 0
    if isinstance(payload, CompareResult) and args.command in {"compare", "diff"}:
        stats = payload.stats
        has_diff = stats.only_in_first_count > 0 or stats.only_in_second_count > 0
        has_duplicates = stats.duplicate_first_count > 0 or stats.duplicate_second_count > 0
        return 1 if has_diff or has_duplicates else 0
    if args.command == "duplicates":
        if isinstance(payload, list):
            return 1 if payload else 0
        if isinstance(payload, dict):
            return 1 if payload.get("duplicate_count", 0) > 0 else 0
    return 0


def _format_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"uniqdiff: file not found: {exc.filename}"
    if isinstance(exc, PermissionError):
        return f"uniqdiff: permission denied: {exc.filename}"
    return f"uniqdiff: {exc}"


def _atomic_write_json(payload: Any, output: str) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=str(output_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
