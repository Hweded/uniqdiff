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
{"type":"metadata","format":"uniqdiff.jsonl","format_version":"1.0","tool":"uniqdiff","tool_version":"1.0.0","mode":"field_diff","key_columns":["id"],"compared_columns":["status"],"created_at":"2026-05-06T12:00:00Z"}
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

These are real local benchmark runs from this repository. Results depend on CPU,
disk, Python version, input shape, overlap, and output size. They are intended as
fit-by-use-case data, not as a universal speed claim.

Environment for the numbers below:

- date: 2026-05-07;
- Python: 3.14.4;
- pandas: 2.3.3;
- DuckDB: 1.5.2;
- csv-diff: 1.2;
- DataComPy: 0.19.5.

Verification commands run before updating this README:

```bash
python -m ruff check src tests
python -m mypy src
python -m pytest tests -q
```

Result:

```text
ruff: All checks passed
mypy: Success, no issues found in 37 source files
pytest: full test suite passed, 2 optional tests skipped
```

Scalar keyed diff, `100_000` rows per input, `50%` overlap:

```bash
python benchmarks/run.py \
  --size 100000 \
  --chunk-size 50000 \
  --scenario memory \
  --scenario sqlite \
  --scenario file_result \
  --json
```

| Scenario | Backend | Time | Peak memory | Rows only in left | Rows only in right | Common | Output |
|---|---|---:|---:|---:|---:|---:|---:|
| memory | memory | 0.062s | 13.308 MB | 50,000 | 50,000 | 50,000 | 0 MB |
| sqlite | sqlite | 2.451s | 9.206 MB | 50,000 | 50,000 | 50,000 | 0 MB |
| file_result | sqlite | 3.481s | 9.202 MB | 50,000 | 50,000 | 50,000 | 5.759 MB |

Dictionary row diff by `id`, `50_000` rows per input, `50%` overlap:

```bash
python benchmarks/run.py \
  --size 50000 \
  --data-shape dict \
  --chunk-size 25000 \
  --scenario memory \
  --scenario sqlite \
  --scenario file_result \
  --json
```

| Scenario | Backend | Time | Peak memory | Rows only in left | Rows only in right | Common | Output |
|---|---|---:|---:|---:|---:|---:|---:|
| memory | memory | 0.046s | 6.638 MB | 25,000 | 25,000 | 25,000 | 0 MB |
| sqlite | sqlite | 2.506s | 26.818 MB | 25,000 | 25,000 | 25,000 | 0 MB |
| file_result | sqlite | 4.683s | 26.589 MB | 25,000 | 25,000 | 25,000 | 5.057 MB |

What the numbers show:

- memory mode is fastest when data fits comfortably in RAM;
- disk mode trades speed for bounded materialization and file-backed workflows;
- file-result mode handles large outputs without keeping result rows in memory;
- benchmark runs are reproducible with stdlib-only tooling.

Cross-tool benchmarks are available separately:

```bash
pip install -e ".[benchmark]"
python benchmarks/comparison/run.py --profile orders --rows 10000
```

The comparison suite reports fit-by-use-case labels for pandas, DuckDB,
csv-diff/csvdiff-style workflows, DataComPy, and `uniqdiff`.

Cross-tool workload:

- profile: `orders`;
- rows per side: `10,000`;
- overlap: `70%`;
- changed rows among common keys: `20%`;
- duplicates in duplicate workload: `5%`;
- schema columns: `11`.

Fit by use case:

| Scenario | Native | Custom code | Partial | Not primary |
|---|---|---|---|---|
| Row presence by key | uniqdiff, DuckDB | pandas | csv-diff, DataComPy | - |
| Duplicate detection by key | uniqdiff, pandas, DuckDB | - | - | csv-diff, DataComPy |
| Row-level changed fields | uniqdiff, csv-diff, DataComPy | pandas, DuckDB | - | - |
| Large output handling | uniqdiff, DuckDB | - | pandas, csv-diff | DataComPy |

Representative measurements:

| Adapter | Scenario | Support | Time | Peak memory | Rows/s | Expected counts |
|---|---|---|---:|---:|---:|---|
| uniqdiff | row presence | native | 0.321s | 19.854 MB | 62,402 | yes |
| pandas | row presence | custom code | 0.121s | 9.990 MB | 164,769 | yes |
| DuckDB | row presence | native | 0.335s | 0.006 MB tracked by Python | 59,782 | yes |
| csv-diff | row presence | partial | 1.002s | 29.239 MB | 19,958 | yes |
| DataComPy | row presence | partial | 0.627s | 31.403 MB | 31,909 | yes |
| uniqdiff | duplicate detection | native | 0.157s | 10.412 MB | 66,878 | yes |
| pandas | duplicate detection | native | 0.048s | 4.064 MB | 218,736 | yes |
| DuckDB | duplicate detection | native | 0.074s | 0.001 MB tracked by Python | 142,278 | yes |
| uniqdiff | field-level diff | native | 0.342s | 10.104 MB | 58,526 | yes |
| pandas | field-level diff | custom code | 0.106s | 8.341 MB | 188,713 | yes |
| DuckDB | field-level diff | custom code | 0.140s | 0.006 MB tracked by Python | 143,113 | yes |
| csv-diff | field-level diff | native | 0.740s | 21.279 MB | 27,028 | yes |
| DataComPy | field-level diff | native | 0.554s | 28.315 MB | 36,081 | yes |
| uniqdiff | large output | native | 1.185s | 9.199 MB | 16,877 | yes |
| DuckDB | large output | native | 0.132s | 0.003 MB tracked by Python | 151,095 | n/a |

Interpretation:

- pandas and DuckDB can be faster for small/medium in-memory tabular workloads;
- DuckDB memory in this table is Python `tracemalloc`, not full native process memory;
- `uniqdiff` is optimized for a stable Python/CLI comparison engine, exact result
  objects, JSONL events, file-result output, and no required dataframe/SQL runtime;
- for large outputs, benchmark both runtime and output semantics, not just elapsed
  seconds.

## Road to 1.1

Most 1.1 engine work is already in `main`: field-level diff, schema-aware diff,
sorted streaming diff, JSONL event streams, bounded JSONL output, `uniqdiff.engine`,
profiling, and realistic cross-tool benchmarks.

Remaining release work:

- refresh docs/examples for `--max-output-rows` and `--max-output-bytes`;
- add a small compatibility test for `uniqdiff.engine.__all__` in release checks;
- run benchmark profiles on at least `orders`, `wide_orders`, and `large_output`;
- decide whether `compare_fields_sorted()` and schema diff are marked stable 1.1
  or documented as advanced 1.x APIs;
- update release notes and changelog for `1.1.0`;
- build package and run install smoke from wheel;
- tag and publish after CI passes.

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
