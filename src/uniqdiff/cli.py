"""Command line interface for uniqdiff."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff import FieldDiffResult, compare_file_fields, compare_files, duplicates
from uniqdiff.disk import atomic_write_result
from uniqdiff.exceptions import UniqDiffError
from uniqdiff.io.readers import read_file
from uniqdiff.normalizers import string_normalizer
from uniqdiff.result import CompareResult


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the uniqdiff CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        payload = _run_command(args)
    except (OSError, UniqDiffError, ValueError) as exc:
        print(_format_error(exc), file=sys.stderr)
        return 2

    if isinstance(payload, CompareResult):
        return _handle_compare_result(payload, args)
    if isinstance(payload, FieldDiffResult):
        return _handle_field_diff_result(payload, args)
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
        help="Input format: auto, csv, tsv, jsonl, parquet, txt.",
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
            "Return exit code 1 when compare/diff find differences "
            "or duplicates finds duplicates."
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


def _run_command(args: argparse.Namespace) -> Union[CompareResult, FieldDiffResult, list[Any]]:
    key = _parse_key(args.key)
    normalizer = _build_normalizer(args)
    fieldnames = _parse_fieldnames(args.fieldnames)
    columns = _parse_fieldnames(args.columns)

    if args.command == "duplicates":
        return duplicates(
            read_file(
                args.file_a,
                format=args.format,
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

    if getattr(args, "field_diff", False):
        if key is None:
            raise ValueError("--field-diff requires --key")
        return compare_file_fields(
            args.file_a,
            args.file_b,
            format=args.format,
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
        format=args.format,
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


def _list_summary_payload(payload: list[Any], command: str) -> dict[str, Any]:
    count_name = "duplicate_count" if command == "duplicates" else "count"
    return {count_name: len(payload), "empty": len(payload) == 0}


def _exit_code(
    payload: Union[CompareResult, FieldDiffResult, list[Any], dict[str, Any]],
    args: argparse.Namespace,
) -> int:
    if not args.fail_on_diff:
        return 0
    if isinstance(payload, FieldDiffResult) and args.command in {"compare", "diff"}:
        return 1 if payload.stats.changed_row_count > 0 else 0
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
