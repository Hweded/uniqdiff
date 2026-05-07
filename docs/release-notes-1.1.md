# Release Notes 1.1.0

`uniqdiff` 1.1.0 is an additive engine release. It keeps the 1.0 exact comparison
contract and adds production-oriented primitives for structured diff, schema diff,
streaming event output, profiling, and downstream UniqTools integrations.

## Highlights

- Added sorted streaming diff APIs for already sorted inputs:
  `iter_sorted_diff()`, `compare_sorted_iter()`, `write_sorted_diff()`, and
  `write_sorted_diff_file()`.
- Added engine-level field diff by key, including column filters, summary by
  column, JSONL output, output limits, sorted-input mode, and CLI flags.
- Added schema-aware diff for inferred columns, value types, and nullability.
- Added the versioned `uniqdiff.jsonl` event stream with metadata, diff events,
  field/schema events, duplicate-key events, and summary events.
- Added lazy event readers and summary helpers:
  `iter_event_rows()`, `summarize_events()`, and `summarize_event_file()`.
- Added the explicit `uniqdiff.engine` facade for downstream packages that want a
  stable comparison-engine import boundary.
- Improved `mode="auto"` decision metadata and added `disk_strategy="auto"`.
- Improved JSONL/file-output hot paths and composite-key token extraction.
- Added profiling and realistic cross-tool benchmark suites.

## Engine API Additions

New documented APIs include:

- `compare_sorted_iter()`;
- `write_sorted_diff_file()`;
- `compare_fields()`;
- `compare_fields_sorted()`;
- `compare_fields_files()`;
- `compare_fields_files_sorted()`;
- `compare_file_fields()`;
- `compare_file_fields_sorted()`;
- `iter_field_diff_rows()`;
- `iter_field_diff_events()`;
- `iter_sorted_field_diff_events()`;
- `infer_schema()`;
- `compare_schema()`;
- `compare_file_schema()`;
- `iter_compare_events()`;
- `iter_event_rows()`;
- `summarize_events()`;
- `summarize_event_file()`;
- `uniqdiff.engine`.

These are engine primitives. They return structured facts, iterators, or streaming
files. They do not add reports, workflow orchestration, dashboards, or data quality
policy logic to the core package.

## CLI Additions

The CLI now supports:

- `--format jsonl` event streams for compare/diff workflows;
- `--field-diff`;
- `--sorted-input` for low-memory sorted field diff;
- `--exclude-columns`;
- `--max-rows` / `--max-bytes` for field-diff output;
- `--max-output-rows` / `--max-output-bytes` for JSONL event streams;
- `--schema-diff`;
- `--schema-sample-size`;
- `--empty-string-not-null`;
- `--loose-numeric-types`.

`compare --format jsonl` does not emit common-row data events by default. It still
reports `summary.common_rows`, which keeps large machine-readable streams focused
on differences.

## Performance And Benchmarks

1.1 includes:

- stdlib backend benchmark runner improvements;
- cProfile/tracemalloc profiling suite for memory, disk, file-result, and sorted
  streaming modes;
- realistic cross-tool benchmark suite comparing `uniqdiff`, pandas, DuckDB,
  csv-diff, and DataComPy by use case;
- optimized compact JSONL and file-result writing;
- optimized composite dict key token extraction;
- cheaper in-memory duplicate collection.

Benchmark results are workload-dependent. Use `docs/benchmarks.md` and the raw
benchmark runners to reproduce numbers on the target machine and data shape.

## Compatibility

1.1 is backward-compatible with the 1.0 public engine contract.

The `uniqdiff.jsonl` event schema remains format version `1.0`. Package version
and event stream schema version are intentionally separate: `uniqdiff` can ship
new package releases without changing the event schema.

## Supported Python Versions

`uniqdiff` 1.1 supports Python 3.9 through 3.14.

## Optional Extras

Official 1.1 extras:

- `dev`;
- `benchmark`;
- `fuzzy`;
- `parquet`.

## Non-Goals

1.1 keeps the engine boundary intact. It does not add:

- HTML/PDF/Excel reports;
- workflow orchestration;
- data quality rule engines;
- dashboards;
- SaaS or enterprise management logic;
- heavy cloud/database connector management in the core package.
