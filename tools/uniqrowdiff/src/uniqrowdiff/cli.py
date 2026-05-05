"""Command line interface for uniqrowdiff."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from uniqrowdiff import RowDiffSummary, diff_csv_by_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uniqrowdiff",
        description="Compare changed fields for CSV rows with the same key.",
    )
    parser.add_argument("first", help="First CSV file.")
    parser.add_argument("second", help="Second CSV file.")
    parser.add_argument("--key", required=True, help="CSV key column used to match rows.")
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="FIELD",
        help="Field to ignore while comparing changed values. Can be repeated.",
    )
    parser.add_argument("--output", help="Write changed rows as JSONL.")
    parser.add_argument(
        "--mode",
        choices=["memory", "disk", "auto"],
        default="auto",
        help="uniqdiff execution mode used for presence comparison.",
    )
    parser.add_argument(
        "--fail-on-changes",
        action="store_true",
        help="Exit with code 1 when changed rows are found.",
    )
    parser.add_argument(
        "--fail-on-added",
        action="store_true",
        help="Exit with code 1 when rows are present only in the second file.",
    )
    parser.add_argument(
        "--fail-on-removed",
        action="store_true",
        help="Exit with code 1 when rows are present only in the first file.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = diff_csv_by_key(
            Path(args.first),
            Path(args.second),
            key=args.key,
            ignore_fields=args.ignore,
            output=None if args.output is None else Path(args.output),
            mode=args.mode,
        )
    except (OSError, ValueError) as exc:
        print(f"uniqrowdiff: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(result.summary), indent=2, sort_keys=True))
    if _should_fail(args, result.summary):
        return 1
    return 0


def _should_fail(args: argparse.Namespace, summary: RowDiffSummary) -> bool:
    return bool(
        (args.fail_on_changes and summary.changed_rows)
        or (args.fail_on_added and summary.only_in_second)
        or (args.fail_on_removed and summary.only_in_first)
    )


if __name__ == "__main__":
    raise SystemExit(main())
