# uniqdiff

`uniqdiff` is a stable comparison engine foundation for Python projects and the
UniqTools ecosystem. It compares datasets, files, streams, and connector-backed
sources, then returns exact unique differences, intersections, duplicates, result
metadata, and comparison statistics.

Its purpose is to provide stable exact comparison semantics, token extraction,
backends, result objects, lazy result readers, connectors, and a direct CLI.
Product-layer features such as reports, schema validation, data quality rules,
dashboards, and workflow orchestration belong in higher-level UniqTools packages.

## Installation

```bash
pip install uniqdiff
```

Install optional Parquet support:

```bash
pip install "uniqdiff[parquet]"
```

For local development:

```bash
pip install -e ".[dev]"
```

## Documentation

Key guides:

- [Recipes](docs/recipes.md)
- [Stable Engine Contract](docs/stable-engine-contract.md)
- [Engine Boundary](docs/engine-boundary.md)
- [Public API Boundary](docs/public-api.md)
- [API Reference](docs/api-reference.md)
- [Result Schema](docs/result-schema.md)
- [Backend Behavior](docs/backend-behavior.md)
- [Connectors](docs/connectors.md)
- [CLI](docs/cli.md)
- [Migration Guide](docs/migration-guide.md)
- [Backward Compatibility](docs/backward-compatibility.md)
- [Release 1.0 Checklist](docs/release-1.0.md)
- [Release Notes 1.0](docs/release-notes-1.0.md)
- [Release Process](docs/release-process.md)

Project files:

- [License](LICENSE)
- [Commercial Support](COMMERCIAL.md)
- [Support](SUPPORT.md)
- [Services](SERVICES.md)

## Quick Start

```python
from uniqdiff import compare

result = compare([1, 2, 3], [3, 4, 5], include_common=True)

print(result.only_in_first)   # [1, 2]
print(result.only_in_second)  # [4, 5]
print(result.common)          # [3]
print(result.unique)          # [1, 2, 4, 5]
```

## Compare Dictionaries By Key

```python
from uniqdiff import compare_by_key

old = [{"id": 1, "name": "Ann"}, {"id": 2, "name": "Bob"}]
new = [{"id": 2, "name": "Bob"}, {"id": 3, "name": "Cara"}]

result = compare_by_key(old, new, key="id")

assert result.only_in_first == [{"id": 1, "name": "Ann"}]
assert result.only_in_second == [{"id": 3, "name": "Cara"}]
```

## Normalization

```python
from uniqdiff import compare, string_normalizer

normalizer = string_normalizer(lower=True, strip=True, remove_spaces=True)
result = compare([" Alice ", "Bob"], ["alice", "Cara"], normalizer=normalizer)
```

## File Comparison

```python
from uniqdiff import compare_files

result = compare_files("old.csv", "new.csv", key="id", format="csv")
result = compare_files("old.csv", "new.csv", key="id", format="csv", delimiter=";")
result = compare_files("old.parquet", "new.parquet", key="id", columns=("id", "name"))
```

Supported formats:

- `csv`
- `tsv`
- `jsonl`
- `parquet` with `uniqdiff[parquet]`
- `txt`
- gzip-compressed variants such as `.csv.gz`, `.tsv.gz`, `.jsonl.gz`, and `.txt.gz`

## Connectors

Connectors provide a small extension layer for reading data sources. Built-ins cover
iterables and local files:

```python
from uniqdiff import compare_sources

result = compare_sources(
    "old.csv",
    "new.csv",
    first_kind="csv",
    second_kind="csv",
    key="id",
)
```

Registered connector names:

- `iterable`
- `file`
- `csv`
- `tsv`
- `tab`
- `jsonl`
- `parquet`
- `pq`
- `txt`
- `text`

Custom connectors implement `open()` and `describe()` and can be registered with
`register_connector`.

CSV and TSV connectors support dialect options such as `delimiter`, `quotechar`,
`has_header`, and `fieldnames`.

Parquet support is optional and uses `pyarrow`. Install it with `uniqdiff[parquet]`.
The Parquet connector supports `columns` and `batch_size`.

## Disk Mode

`mode="disk"` uses a temporary SQLite database from the Python standard library.
Input iterables are consumed incrementally and indexed on disk, which is useful when
the input data should not be fully materialized as Python sets.

```python
from uniqdiff import compare

result = compare(
    stream_a,
    stream_b,
    key="id",
    mode="disk",
    disk_strategy="sqlite",
    chunk_size=100_000,
    temp_dir="./tmp",
    disk_limit="10GB",
)
```

`mode="auto"` uses a small, predictable heuristic:

- `result_mode="file"` chooses disk mode;
- `temp_dir` chooses disk mode;
- `memory_limit` is compared with an estimated input size;
- unsized iterables/generators choose disk mode when `memory_limit` is set;
- otherwise auto keeps the memory backend.

The current size estimate for sized inputs is intentionally conservative and simple:
`len(first) + len(second)` multiplied by an internal per-item estimate. The decision is
stored in `result.metadata["auto_decision"]`.

```python
result = compare(
    rows_a,
    rows_b,
    mode="auto",
    memory_limit="512MB",
)

print(result.metadata["backend"])
print(result.metadata["auto_decision"])
```

For very large inputs, hash partitioning can reduce peak memory by comparing one
partition at a time. It is a stable 1.0 backend documented as an advanced mode because
partition count, key skew, and temporary disk usage matter:

```python
result = compare(
    stream_a,
    stream_b,
    key="id",
    mode="disk",
    disk_strategy="hash_partition",
    partition_count=128,
    temp_dir="./tmp",
)
```

Hash partitioning writes temporary partition files and guarantees that equal comparison
tokens are processed in the same partition.

External sort is also available when sorted chunk files are a better fit than
partition files. It is also a stable 1.0 backend documented as an advanced mode:

```python
result = compare(
    stream_a,
    stream_b,
    key="id",
    mode="disk",
    disk_strategy="external_sort",
    chunk_size=250_000,
    temp_dir="./tmp",
)
```

This backend sorts each chunk on disk, performs a merge pass over both sorted token
streams, and emits each result section in original input order for that side. Ordering
is still not part of the cross-backend semantic contract.

## File Result Mode

For large outputs, use `result_mode="file"` with `.jsonl` or `.csv` output. In this
mode, result rows are written to disk and are not materialized in `CompareResult`.
Statistics and metadata are still returned.

```python
result = compare(
    stream_a,
    stream_b,
    key="id",
    mode="disk",
    disk_strategy="sqlite",
    result_mode="file",
    output="diff.jsonl",
)

print(result.stats.only_in_first_count)
print(result.metadata["output"])
```

Read large result files lazily:

```python
from uniqdiff import iter_result_values

for value in iter_result_values("diff.jsonl", sections=("only_in_first",)):
    print(value)
```

File-backed `CompareResult` objects can also stream values:

```python
for value in result.iter_unique():
    print(value)
```

Each JSONL/CSV row contains:

- `section`: `only_in_first`, `only_in_second`, `common`, `duplicates_first`, or `duplicates_second`;
- `value`: the original item.

## CLI

After installation, `uniqdiff` can compare files from the command line:

```bash
uniqdiff compare old.csv new.csv --format csv --key id
uniqdiff compare old.csv new.csv --format csv --key id --summary
uniqdiff diff old.csv new.csv --format csv --key id --summary --fail-on-diff
uniqdiff compare old.csv new.csv --format csv --key id --mode disk --disk-strategy hash-partition
uniqdiff compare old.csv new.csv --format csv --key id --mode disk --disk-strategy external-sort
uniqdiff compare old.csv new.csv --format csv --key id --mode disk --result-mode file --output diff.jsonl
uniqdiff diff old.txt new.txt --format txt --output result.json
uniqdiff intersection old.jsonl new.jsonl --format jsonl --key id
uniqdiff duplicates users.csv --format csv --key email
```

Useful CI flags:

- `--summary`: print compact counters instead of full result rows;
- `--fail-on-diff`: return exit code `1` when `compare`/`diff` find differences or `duplicates` finds duplicates.

Common options:

- `--mode memory|disk|auto`
- `--chunk-size 100000`
- `--memory-limit 512MB`
- `--temp-dir ./tmp`
- `--disk-limit 10GB`
- `--disk-strategy sqlite|hash-partition|external-sort`
- `--partition-count 128`
- `--result-mode memory|file`
- `--lower`
- `--remove-spaces`
- `--remove-special`

## Benchmarks

Run local benchmark scenarios with:

```bash
python benchmarks/run.py --size 100000
```

For a quick smoke run:

```bash
python benchmarks/run.py --size 1000 --scenario memory --scenario sqlite
```

The benchmark runner reports elapsed time, peak memory, result counts, and output file
size for file-result scenarios.

## Commercial Support

`uniqdiff` Core is free and open-source under the Apache License 2.0. Basic
comparison, local file support, CLI usage, exact backends, file result mode, lazy
readers, and the public engine API are not paid features.

Commercial support is available for teams that need production integration,
performance audits, CI/CD workflows, custom connectors, row-level diff, or reporting
through the broader UniqTools ecosystem.

See [COMMERCIAL.md](COMMERCIAL.md), [SUPPORT.md](SUPPORT.md), and
[SERVICES.md](SERVICES.md).

Contact: `dredpirite@gmail.com`

## Fuzzy Comparison

Approximate string comparison is available through a separate API so exact comparison
semantics stay unchanged:

```python
from uniqdiff import compare_fuzzy_strings, string_normalizer

result = compare_fuzzy_strings(
    ["Alice Smith"],
    ["alice smyth"],
    threshold=75,
    normalizer=string_normalizer(lower=True),
)
```

Install `uniqdiff[fuzzy]` to use `rapidfuzz`; otherwise the stdlib `difflib` fallback is
used. Fuzzy comparison is approximate, greedy, and `O(n*m)`. It is a helper API, not
part of the exact comparison engine.

## Bloom Filter Candidates

Bloom filter helpers are available for approximate candidate filtering:

```python
from uniqdiff import probabilistic_diff_candidates

result = probabilistic_diff_candidates(
    old_ids,
    new_ids,
    expected_first=1_000_000,
    expected_second=1_000_000,
)
```

Bloom filters can produce false positives. In candidate-diff workflows, a false
positive can hide a true difference, so this helper is not a replacement for exact
comparison when every difference must be returned.

## Stable 1.0 Scope

The stable 1.0 engine provides:

- list/tuple/set/iterable comparison;
- dictionary/object/dataclass comparison by key;
- recursive canonicalization for non-hashable structures;
- optional normalization;
- duplicate detection;
- file readers for CSV, JSONL, and text;
- connector API for iterable and file-backed sources;
- CLI commands for compare, diff, intersection, and duplicates;
- SQLite-backed disk mode for exact comparison without optional dependencies;
- hash partitioning disk strategy for partition-by-partition comparison;
- external sort disk strategy for sorted chunk and merge comparison;
- file result mode for streaming large results to JSONL/CSV output;
- approximate fuzzy string comparison as a helper outside exact semantics;
- Bloom filter helpers for probabilistic candidate filtering outside exact semantics;
- property-based tests that compare backend semantics;
- benchmark runner for memory and disk strategies;
- result serialization to dict, JSON, JSONL, and CSV;
- stable API parameters for `memory`, `disk`, and `auto` modes.

Lazy result readers are already available for JSONL/CSV file-result outputs.
