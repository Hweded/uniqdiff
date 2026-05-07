# Benchmarks

Benchmark results are workload-dependent. Use these numbers to understand fit by
use case and to reproduce runs on your own machine, not to claim one universal
winner.

## Environment

Recent README benchmark data was generated on 2026-05-07 with:

- Python 3.14.4;
- pandas 2.3.3;
- DuckDB 1.5.2;
- csv-diff 1.2;
- DataComPy 0.19.5.

Verification commands:

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

## Backend Benchmarks

Run the backend benchmark suite:

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

### Recent Backend Results

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

Interpretation:

- memory mode is fastest when data fits comfortably in RAM;
- disk mode trades speed for bounded materialization and file-backed workflows;
- file-result mode handles large outputs without keeping result rows in memory.

## Cross-Tool Benchmarks

Install optional benchmark dependencies:

```bash
pip install -e ".[benchmark]"
```

Run the realistic order-shaped workload:

```bash
python benchmarks/comparison/run.py --profile orders --rows 10000
```

Workload:

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

## Output Files

Generated benchmark outputs are ignored by git:

- `benchmarks/results/`;
- `benchmarks_tmp/`;
- `benchmarks/.tmp/`.

Keep raw JSONL/Markdown benchmark outputs in GitHub Releases or external reports
when publishing performance claims.
