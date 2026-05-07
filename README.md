# uniqdiff

Data diff engine for CSV, Parquet, JSONL, streams, and large dataset comparison.

`uniqdiff` tells you what changed between two datasets:

- rows only in the old dataset;
- rows only in the new dataset;
- rows present in both datasets;
- changed fields for rows with the same key;
- schema drift: added/removed columns, type changes, nullable changes.

It is built for data engineers, backend engineers, ETL pipelines, and data QA jobs
that need repeatable diffs without writing pandas merge code or DuckDB SQL.

```bash
pip install uniqdiff
uniqdiff diff old.csv new.csv --format csv --key id --summary
```

## Why uniqdiff

- **Less memory than pandas for large diffs**: use disk-backed and file-result modes.
- **Simpler than DuckDB for comparison jobs**: no SQL required.
- **More scalable than csv-diff for large outputs**: stream JSONL/CSV result rows.
- **Engine-first API**: use it from Python, CLI, CI, ETL, or other tools.
- **No heavy required dependencies**: core uses the Python standard library.

Use `uniqdiff` when you need a focused comparison engine, not a dataframe framework,
SQL database, or report generator.

## Quick start

Create two files:

```bash
python -c "from pathlib import Path; Path('old.csv').write_text('id,name,status\n1,Alice,active\n2,Bob,pending\n3,Cara,active\n', encoding='utf-8'); Path('new.csv').write_text('id,name,status\n2,Bob,active\n3,Cara,active\n4,Dana,pending\n', encoding='utf-8')"
```

Install and compare:

```bash
pip install uniqdiff
uniqdiff diff old.csv new.csv --format csv --key id --summary
```

Find changed fields for matching keys:

```bash
uniqdiff diff old.csv new.csv --format csv --key id --field-diff
```

Use the sorted streaming path when upstream exports are already sorted by key:

```bash
uniqdiff diff old.csv new.csv --format csv --key id --field-diff --sorted-input
```

Check schema drift:

```bash
uniqdiff diff old.csv new.csv --format csv --schema-diff --summary
```

Use from Python:

```python
from uniqdiff import compare

result = compare(
    [{"id": 1}, {"id": 2}],
    [{"id": 2}, {"id": 3}],
    key="id",
    include_common=True,
)

print(result.only_in_first)   # [{"id": 1}]
print(result.only_in_second)  # [{"id": 3}]
print(result.common)          # [{"id": 2}]
```

## Example output

CLI summary:

```json
{
  "equal": false,
  "only_in_first_count": 1,
  "only_in_second_count": 1,
  "common_count": 2,
  "duplicate_first_count": 0,
  "duplicate_second_count": 0,
  "backend": "memory",
  "result_mode": "memory"
}
```

Field-level diff:

```json
{
  "rows": [
    {
      "key": "2",
      "changes": [
        {
          "field": "status",
          "left": "pending",
          "right": "active"
        }
      ]
    }
  ],
  "summary_by_column": {
    "status": 1
  }
}
```

Machine-readable JSONL event stream:

```bash
uniqdiff diff old.csv new.csv \
  --key id \
  --field-diff \
  --columns status \
  --format jsonl \
  --output diff.jsonl
```

Example `uniqdiff.jsonl` events:

```jsonl
{"type":"metadata","format":"uniqdiff.jsonl","format_version":"1.0","tool":"uniqdiff","tool_version":"1.1.0","mode":"field_diff","key_columns":["id"],"compared_columns":["status"],"created_at":"2026-05-06T12:00:00Z"}
{"type":"only_left","key":{"id":"1"}}
{"type":"field_change","key":{"id":"2"},"column":"status","left":"pending","right":"active"}
{"type":"summary","left_rows":3,"right_rows":3,"common_rows":2,"only_left":1,"only_right":1,"changed_rows":1,"changed_fields":1,"duplicate_keys_left":0,"duplicate_keys_right":0,"schema_changes":0}
```

Legacy `section`/`value` file-result output:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --mode disk \
  --result-mode file \
  --output diff.jsonl
```

Example JSONL rows:

```jsonl
{"section":"only_in_first","value":{"id":"1","name":"Alice","status":"active"}}
{"section":"only_in_second","value":{"id":"4","name":"Dana","status":"pending"}}
```

## Use cases

- Compare daily CSV exports.
- Detect added and removed records by primary key.
- Compare Parquet snapshots in ETL pipelines.
- Catch row-level changes before loading data downstream.
- Detect schema drift in CI.
- Stream large diff outputs to JSONL for later processing.
- Load diff events into DuckDB, Spark, BigQuery, ClickHouse, or CI jobs.
- Validate backend service exports against expected data.
- Build data QA tools on top of a stable comparison engine.

## Benchmarks

Benchmarks are workload-dependent. The project keeps reproducible benchmark
runners for both internal backends and cross-tool comparison.

```bash
python benchmarks/run.py \
  --size 100000 \
  --chunk-size 50000 \
  --scenario memory \
  --scenario sqlite \
  --scenario file_result \
  --json

pip install -e ".[benchmark]"
python benchmarks/comparison/run.py --profile orders --rows 10000
```

Recent local backend run, Python 3.14.4:

| Workload | Mode | Time | Peak memory | Output |
|---|---|---:|---:|---:|
| 100k scalar rows per side | memory | 0.062s | 13.308 MB | 0 MB |
| 100k scalar rows per side | sqlite | 2.451s | 9.206 MB | 0 MB |
| 100k scalar rows per side | file_result | 3.481s | 9.202 MB | 5.759 MB |
| 50k dict rows per side | memory | 0.046s | 6.638 MB | 0 MB |
| 50k dict rows per side | sqlite | 2.506s | 26.818 MB | 0 MB |
| 50k dict rows per side | file_result | 4.683s | 26.589 MB | 5.057 MB |

Recent cross-tool `orders` run, 10k rows per side:

| Scenario | Native fit | Notes |
|---|---|---|
| Row presence by key | uniqdiff, DuckDB | pandas needs merge code; csv-diff/DataComPy are partial fits. |
| Duplicate detection by key | uniqdiff, pandas, DuckDB | csv-diff/DataComPy are not primary duplicate tools. |
| Row-level changed fields | uniqdiff, csv-diff, DataComPy | pandas/DuckDB need custom comparison code. |
| Large output handling | uniqdiff, DuckDB | pandas often materializes dataframes; DataComPy targets reports. |

Full benchmark commands, environment, raw numbers, and interpretation live in
[docs/benchmarks.md](docs/benchmarks.md).

## Features

- Exact row presence diff:
  - `only_in_first`
  - `only_in_second`
  - `common`
  - `unique`
- Duplicate detection.
- Comparison by key or composite key.
- Field-level diff by key.
- Schema-aware diff:
  - added columns;
  - removed columns;
  - type changes;
  - nullable changes.
- CSV, TSV, JSONL, TXT, gzip, and optional Parquet.
- Streaming sorted diff for already sorted inputs.
- Memory, SQLite, hash partition, external sort, and auto modes.
- File-result mode for JSONL/CSV output.
- `uniqdiff.jsonl` event stream with schema version `1.0`.
- Lazy readers for large result files.
- CLI with `--summary` and `--fail-on-diff`.
- Type hints and stable result objects.

## Usage

Compare files:

```bash
uniqdiff diff old.csv new.csv --format csv --key id
```

Compact CI output:

```bash
uniqdiff diff expected.csv actual.csv \
  --format csv \
  --key id \
  --summary \
  --fail-on-diff
```

Field-level diff:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --field-diff \
  --columns name,status,email \
  --summary
```

Schema diff:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --schema-diff \
  --summary \
  --fail-on-diff
```

Large output:

```bash
uniqdiff diff old.csv new.csv \
  --key id \
  --format jsonl \
  --output diff.jsonl
```

Use `--input-format csv` when file extensions are not enough for input detection:

```bash
uniqdiff diff snapshot_a snapshot_b \
  --input-format csv \
  --key id \
  --format jsonl
```

Python API:

```python
from uniqdiff import (
    compare_fields,
    compare_file_schema,
    compare_files,
    iter_compare_events,
    iter_event_rows,
    iter_field_diff_sorted,
    summarize_event_file,
)

rows = compare_files("old.csv", "new.csv", format="csv", key="id")
fields = compare_fields(old_rows, new_rows, key="id", columns=("status",))
streamed_fields = iter_field_diff_sorted(old_rows_sorted, new_rows_sorted, key="id")
schema = compare_file_schema("old.csv", "new.csv", format="csv")
events = iter_compare_events(old_rows, new_rows, key="id")
saved_events = iter_event_rows("diff.jsonl")
summary = summarize_event_file("diff.jsonl")
```

JSONL event types:

| Type | Meaning |
|---|---|
| `metadata` | First event; format, version, key columns, compared columns, timestamp |
| `only_left` | Key exists only in the left input |
| `only_right` | Key exists only in the right input |
| `row_changed` | Matching-key row has one or more changed fields |
| `field_change` | One changed field with left/right values |
| `duplicate_key` | Duplicate key detected on one side |
| `schema_change` | Added/removed/type/nullable schema change |
| `error` | Machine-readable error event for integrations |
| `summary` | Last event; counts and metrics |

The event stream format name is `uniqdiff.jsonl`; the schema version is `1.0`.
The JSON Schema lives at `docs/schemas/uniqdiff-jsonl-1.0.schema.json`.

Parquet:

```bash
pip install "uniqdiff[parquet]"
```

```python
from uniqdiff import compare_files

result = compare_files(
    "old.parquet",
    "new.parquet",
    format="parquet",
    key="id",
    columns=("id", "status"),
)
```

## Comparison

| Need | uniqdiff | pandas | DuckDB | csv-diff |
|---|---|---|---|---|
| Simple keyed row diff | Built in | Custom merge code | SQL query | Built in |
| Field-level diff | Built in | Custom code | SQL/custom code | Partial |
| Schema drift check | Built in | Custom code | SQL/custom code | No |
| Low-memory output | JSONL/CSV streaming | Manual | Possible with SQL/export | Limited |
| No SQL required | Yes | Yes | No | Yes |
| Parquet support | Optional extra | Yes | Yes | No/limited |
| CI-friendly CLI | Yes | No | Partial | Yes |
| Large output handling | Designed for file-result mode | Often materialized | Good with query design | Less scalable |

Choose `uniqdiff` when the job is comparison.

Choose pandas when the job is dataframe transformation.

Choose DuckDB when the team wants SQL and query planning.

Choose csv-diff for small CSV-only diffs.

## How it works

`uniqdiff` is an engine layer:

```text
input source
  -> reader / connector
  -> key extraction and normalization
  -> backend selection
  -> exact comparison
  -> memory result or streaming file result
```

Backends:

- `memory`: fastest path for small and medium datasets.
- `sqlite`: disk-backed exact comparison with no optional dependency.
- `hash_partition`: splits data into hash partitions for large comparisons.
- `external_sort`: sorts chunks on disk and merges token streams.
- `auto`: chooses a backend from input/options metadata.

Result modes:

- `memory`: returns Python result objects.
- `file`: streams JSONL/CSV output and returns stats/metadata.

Engine boundaries:

- `uniqdiff` does comparison.
- Reports, dashboards, workflow orchestration, cloud connector management, and
  business rules belong in higher-level tools such as UniqTools.

## Limitations

- Memory mode is fastest but requires data/results to fit in RAM.
- Disk mode is slower because it uses temporary storage.
- File-result mode avoids materializing output rows, but output size still affects runtime.
- Field-level diff currently indexes the second input by key.
- Schema inference is based on observed values, not database DDL.
- Parquet requires `pyarrow` via `uniqdiff[parquet]`.
- Fuzzy matching and Bloom filters are helper APIs, not replacements for exact diff.
- Benchmark results are workload-dependent; run the included benchmark suite on your data shape.

## Call to action

If `uniqdiff` helps you compare datasets with less code and safer memory behavior,
star the repository.

Stars help more data engineers and backend engineers find the project, and they
make it easier to keep improving the engine.
