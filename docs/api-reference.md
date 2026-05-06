# API Reference

## `compare(first, second, ...)`

Universal comparison entry point.

Important parameters:

- `key`: string, tuple/list of strings, callable, or `None`;
- `normalizer`: callable applied after key extraction;
- `mode`: `memory`, `disk`, or `auto`;
- `disk_strategy`: `sqlite`, `hash_partition`, or `external_sort`;
- `result_mode`: `memory` or `file`;
- `output`: JSON, JSONL, or CSV path depending on mode;
- `include_common`: include intersection;
- `include_duplicates`: include duplicate sections;
- `chunk_size`: batch size for disk strategies;
- `memory_limit`: used by `mode="auto"`;
- `disk_limit`: safety limit for temporary disk usage;
- `temp_dir`: temporary storage directory;
- `preserve_order`: keep first-seen order in memory mode. Set `False` when output
  order is not important and set-style key operations are acceptable.

Returns `CompareResult`.

## `diff(first, second, ...)`

Convenience wrapper around `compare` with `include_common=False`.

## `unique(first, second, ...)`

Returns a list containing values that appear in only one input.

## `intersection(first, second, ...)`

Returns values present in both inputs.

## `duplicates(data, ...)`

Finds duplicate values within one input.

## `compare_by_key(first, second, key=...)`

Compares structured values by dictionary key, object attribute, dataclass field, or
compound key.

## `compare_by_hash(first, second, algorithm="sha256")`

Compares values by stable cryptographic hash of the canonical representation.

## `compare_fields(first, second, key=...)`

Compares structured rows that share the same key and returns field-level changes.
This is intended for engine-level row diff workflows, not formatted reports.

Important parameters:

- `key`: required row key;
- `columns`: optional fields to compare;
- `exclude_columns`: fields to ignore;
- `normalizer`: optional value normalizer before comparison;
- `output`: optional `.jsonl` path for streaming changed rows;
- `max_rows`: maximum changed rows to emit;
- `max_bytes`: maximum JSONL output bytes when streaming.

Returns `FieldDiffResult` with:

- `rows`: changed rows when no output file is used;
- `summary_by_column`: changed-field counts by column;
- `stats`: counts, truncation flag, and output bytes;
- `metadata`;
- `warnings`.

Streaming JSONL rows use this shape:

```python
{"key": row_key, "changes": [{"field": "status", "left": "old", "right": "new"}]}
```

## `compare_fields_files(file_a, file_b, key=...)`

Reads supported files and runs `compare_fields()`. CSV, TSV, JSONL, TXT, and
Parquet inputs follow the same reader options as `compare_files()`.

## `compare_file_fields(file_a, file_b, key=...)`

Alias-style public facade for file-oriented field comparison.

## `iter_field_diff_rows(output)`

Lazily reads JSONL rows produced by field-level diff streaming output.

Each yielded row contains:

- `key`;
- `changes`.

## `infer_schema(rows, ...)`

Infers column names, observed value types, and nullability from structured rows.

Important parameters:

- `sample_size`: optional maximum rows to inspect;
- `empty_string_null`: treat empty strings as null-like values when `True`;
- `strict_numeric_types`: keep `int` and `float` separate when `True`, or infer
  both as `number` when `False`.

Returns `SchemaResult`.

## `compare_schema(first, second, ...)`

Infers and compares schemas for two structured inputs.

The result reports:

- `added_columns`;
- `removed_columns`;
- `type_changes`;
- `nullable_changes`;
- `left_schema`;
- `right_schema`;
- `warnings`.

Returns `SchemaDiffResult`.

## `compare_file_schema(file_a, file_b, ...)`

Reads supported files and runs schema-aware diff. It accepts the same file reader
options as `compare_files()` plus `sample_size`, `empty_string_null`, and
`strict_numeric_types`.

## `compare_files(file_a, file_b, ...)`

Reads supported files and compares their rows/items.

Supported formats:

- `csv`;
- `tsv`;
- `jsonl`;
- `parquet` with `uniqdiff[parquet]`;
- `txt`;
- `auto` by extension.

Plain and gzip-compressed files are supported. Auto-detection recognizes extensions
such as `.csv`, `.csv.gz`, `.tsv`, `.tsv.gz`, `.jsonl`, `.jsonl.gz`, `.txt`, and
`.txt.gz`.

Parquet options:

- `columns`: optional list/tuple of columns to read;
- `batch_size`: number of rows per Parquet batch.

CSV/TSV options:

- `delimiter`: delimiter override;
- `quotechar`: quote character;
- `has_header`: whether the first row contains column names;
- `fieldnames`: field names for headerless CSV/TSV files.

## `compare_iter(first, second, ...)`

Alias for iterable/generator-oriented usage.

## `iter_compare_events(first, second, ...)`

Yields a `uniqdiff.jsonl` event stream as dictionaries. The first yielded event is
`metadata`; the last yielded event is `summary`.

Important parameters:

- `key`: string, tuple/list of strings, callable, or `None`;
- `normalizer`: callable applied after key extraction;
- `mode`: `memory`, `disk`, or `auto`;
- `include_common`: include common-row counts;
- `include_duplicates`: emit duplicate-key events when duplicate rows are collected;
- `compared_columns`: optional metadata for downstream tools.

This API is designed for callers that want to write JSONL incrementally instead of
building one large output object.

## `iter_event_rows(output, validate_sequence=True)`

Lazily reads rows from a `uniqdiff.jsonl` event stream.

Behavior:

- validates that every line is a JSON object;
- validates required fields for each event type;
- validates `metadata.format == "uniqdiff.jsonl"`;
- validates `metadata.format_version == "1.0"`;
- when `validate_sequence=True`, requires the first event to be `metadata` and the
  last event to be `summary`.

Raises `InvalidInputError` for malformed streams.

## `compare_sorted_iter(first, second, ...)`

Streams exact `section`/`value` rows for iterable inputs that are already sorted
by comparison token. This is the higher-level engine convenience wrapper around
`iter_sorted_diff()`.

It accepts `key`, `normalizer`, `include_common`, `include_duplicates`, and
`validate_sorted`.

It returns an iterator, not `CompareResult`.

## `write_sorted_diff(first, second, output, ...)`

Writes exact sorted streaming diff rows directly to a `.jsonl` or `.csv` file and
returns the number of rows written.

This helper uses the same sorted-input requirements and row schema as
`iter_sorted_diff()`.

## `write_sorted_diff_file(first, second, output, ...)`

Engine facade wrapper around `write_sorted_diff()`. Use this when you want the
public API naming to clearly communicate that output is written to a result file.

## `compare_streams(stream_a, stream_b, ...)`

Alias for file-like or streaming parsed inputs.

## `compare_sources(first_source, second_source, ...)`

Compares data from connector-backed sources.

Important parameters:

- `first_kind`;
- `second_kind`;
- `first_options`;
- `second_options`.

If kind is omitted, strings and `Path` values use the `file` connector; other values
use the `iterable` connector.

## `duplicates_source(source, ...)`

Finds duplicates in a connector-backed source.

## `iter_result_rows(output, sections=None)`

Lazily reads rows from a `.jsonl` or `.csv` file produced by `result_mode="file"`.
Each yielded row contains `section` and `value`.

## `iter_result_values(output, sections=None)`

Lazily reads only values from a `.jsonl` or `.csv` result file. Use `sections` to
filter result sections such as `only_in_first` or `only_in_second`.

## `iter_sorted_diff(first, second, ...)`

Streams exact diff rows for inputs that are already sorted by comparison token.

Important parameters:

- `key`: string, tuple/list of strings, callable, or `None`;
- `normalizer`: callable applied after key extraction;
- `include_common`: emit `common` rows;
- `include_duplicates`: emit `duplicates_first` and `duplicates_second` rows;
- `validate_sorted`: validate non-descending token order while reading.

Each yielded row uses the file-result row schema:

```python
{"section": "only_in_first", "value": item}
```

This helper does not create temporary files and does not build a full in-memory
index. It keeps only the current equal-token group from each input in memory. It
requires both inputs to be sorted by the same `key` and `normalizer`.

## `CompareResult.iter_unique()`

Yields unique differences. For file-backed results, reads values lazily from the
result file instead of materializing the output in memory.

## `CompareResult.iter_section(section)`

Yields values from one result section from either in-memory result lists or
file-backed output.

## Connector API

Connectors are lightweight source adapters. A connector must provide:

- `name`;
- `open()`;
- `describe()`.

Public built-ins:

- `IterableConnector(source)`: wraps an already parsed iterable;
- `FileConnector(path, format="auto", encoding="utf-8", ...)`: reads supported files;
- `CSVConnector(path, encoding="utf-8")`;
- `TSVConnector(path, encoding="utf-8")`;
- `JSONLConnector(path, encoding="utf-8")`;
- `ParquetConnector(path, columns=None, batch_size=65536)`;
- `TextConnector(path, encoding="utf-8")`.

Registry helpers:

- `connect(source, kind=None, **options)`: creates a connector or passes an existing connector through;
- `create_connector(name, source, **options)`: creates a connector by registered name;
- `register_connector(name, factory)`: registers a custom connector factory;
- `list_connectors()`: returns registered connector names.

`connect()` infers `file` for strings and `Path` values, otherwise it uses `iterable`.

CSV and TSV connectors accept `delimiter`, `quotechar`, `has_header`, and
`fieldnames`.

Parquet connector names are `parquet` and `pq`. Parquet support requires `pyarrow`;
install it with `pip install "uniqdiff[parquet]"`.
