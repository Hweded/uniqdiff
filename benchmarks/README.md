# Benchmarks

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

Large target scenarios for release reports:

- 1 million scalar values;
- 10 million scalar values;
- 100 million scalar values where the machine has enough disk space;
- memory vs SQLite vs hash partitioning vs external sort;
- file result mode for large differences.
