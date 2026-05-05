# Benchmarks

Run benchmarks:

```bash
python benchmarks/run.py --size 100000
```

Run selected scenarios:

```bash
python benchmarks/run.py --size 1000 --scenario memory --scenario sqlite --json
```

Run structured row benchmarks:

```bash
python benchmarks/run.py --size 10000 --data-shape dict --scenario memory --scenario sqlite
```

Write a JSON report:

```bash
python benchmarks/run.py --size 100000 --output benchmark-report.json
```

Measured values:

- elapsed time;
- peak memory from `tracemalloc`;
- throughput in input items per second;
- result counts;
- output bytes for file-result scenarios.

Scenarios:

- `memory`;
- `auto_memory`;
- `auto_disk`;
- `sqlite`;
- `hash_partition`;
- `external_sort`;
- `file_result`.

Data shapes:

- `int`: simple scalar values;
- `dict`: structured rows compared by `id`.

Benchmark results are machine-dependent. Use them to compare strategies on your own
hardware and data shape.
