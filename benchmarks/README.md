# Benchmarks

This directory contains two benchmark groups:

- `benchmarks/run.py`: focused `uniqdiff` backend benchmarks.
- `benchmarks/comparison/`: neutral cross-tool comparison against pandas, DuckDB,
  csv-diff/csvdiff-style workflows, and DataComPy.

Cross-tool benchmark dependencies are optional and must not be added to core
runtime dependencies:

```bash
pip install -e ".[benchmark]"
python benchmarks/comparison/run.py --rows 10000
```

The cross-tool suite is intentionally fit-by-use-case oriented. It reports
support levels, setup complexity, elapsed time, peak Python memory, output size,
deterministic expected-count validation, workload metadata, and a
workload-dependent disclaimer instead of claiming that one tool is universally
faster.

Concrete workload profiles:

- `orders`: default order-like rows with mixed column types.
- `wide_orders`: wider rows for field-diff and row-width pressure.
- `large_output`: lower overlap and larger payloads for file/stream output paths.

Examples:

```bash
python benchmarks/comparison/run.py --profile orders --rows 10000
python benchmarks/comparison/run.py --profile wide_orders --rows 50000
python benchmarks/comparison/run.py --profile large_output --rows 100000 \
  --scenario large_output_handling
```

## uniqdiff backend benchmarks

Run local benchmarks with:

```bash
python benchmarks/run.py --size 100000
```

The runner uses only the Python standard library and reports:

- wall-clock time;
- peak memory from `tracemalloc`;
- result section counts;
- file output size for `result_mode="file"`.

Available scenarios:

- 1 million scalar values in memory mode;
- 10 million scalar values in memory and auto modes;
- CSV/JSONL comparison by key;
- duplicate detection;
- SQLite disk mode comparison;
- hash partitioning disk mode comparison;
- external sort disk mode comparison.

For a fast smoke run:

```bash
python benchmarks/run.py --size 1000 --scenario memory --scenario sqlite
```

For JSON output:

```bash
python benchmarks/run.py --size 100000 --json
```

## uniqdiff mode profiling

Use `benchmarks/profile_modes.py` when you need bottleneck-level profiling rather
than only elapsed time and memory summaries:

```bash
python benchmarks/profile_modes.py --size 20000
```

The profiler uses standard-library `cProfile` and `tracemalloc`, then writes:

- `benchmarks/results/profile-results.jsonl`;
- `benchmarks/results/profile-report.md`.

Profiled scenarios:

- `memory`;
- `memory_no_order`;
- `sqlite`;
- `hash_partition`;
- `external_sort`;
- `file_result`;
- `sorted_stream`;
- `sorted_stream_file`.

For a focused run:

```bash
python benchmarks/profile_modes.py --size 10000 --scenario memory --scenario sqlite
```

Large target scenarios for release reports:

- 1 million scalar values;
- 10 million scalar values;
- 100 million scalar values where the machine has enough disk space;
- memory vs SQLite vs hash partitioning vs external sort;
- file result mode for large differences.
