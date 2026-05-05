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
- `temp_dir`: temporary storage directory.

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
