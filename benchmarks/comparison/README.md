# Cross-Tool Comparison Benchmarks

This benchmark suite compares `uniqdiff` with adjacent Python/data tools in the
same workload shapes:

- `uniqdiff`
- `pandas`
- `DuckDB`
- `csv-diff` / `csvdiff` style workflows
- `DataComPy`

The goal is not to prove that one tool is universally faster. Results are
workload-dependent and should be read as a fit-by-use-case report: which tool has
native support, which one needs custom code, and what trade-offs show up for time,
memory, output size, and implementation complexity.

## Install

Core `uniqdiff` dependencies stay minimal. Benchmark dependencies are optional:

```bash
pip install -e ".[benchmark]"
```

You can also run only the `uniqdiff` adapter without installing the optional
benchmark dependencies:

```bash
python benchmarks/comparison/run.py --adapter uniqdiff --rows 1000
```

## Scenarios

| Scenario | Purpose |
| --- | --- |
| `row_presence_by_key` | CSV row presence by key: `only_in_left`, `only_in_right`, `common`. |
| `duplicate_detection_by_key` | Duplicate detection inside a single CSV by key. |
| `row_level_changed_fields_by_key` | Count changed rows and changed fields for common keys. |
| `large_output_handling` | Exercise file/large-output paths instead of only in-memory results. |
| `implementation_setup_complexity` | Capture install/setup shape and typical code complexity. |

## Support Labels

| Label | Meaning |
| --- | --- |
| `native` | Directly supported by the tool's primary API or query model. |
| `custom_code` | Possible, but requires user-written glue logic. |
| `partial` | Supported only for part of the scenario. |
| `not_supported` | No adapter implementation or practical support in this suite. |
| `not_primary_use_case` | Possible in some form, but not what the tool is mainly for. |

## Run

Run all adapters and scenarios:

```bash
python benchmarks/comparison/run.py --rows 10000
```

Run selected adapters:

```bash
python benchmarks/comparison/run.py --adapter uniqdiff --adapter duckdb --rows 100000
```

Run selected scenarios:

```bash
python benchmarks/comparison/run.py \
  --scenario row_presence_by_key \
  --scenario large_output_handling \
  --rows 100000
```

Keep generated input CSV files for inspection:

```bash
python benchmarks/comparison/run.py --rows 1000 --keep-data
```

By default, output is written to:

- `benchmarks/results/comparison/results.jsonl`
- `benchmarks/results/comparison/report.md`

## Dataset

The generator is deterministic. It writes:

- `left.csv`
- `right.csv`
- `duplicates.csv`

Controls:

- `--rows`
- `--seed`
- `--overlap-ratio`
- `--changed-ratio`
- `--duplicate-ratio`

Example:

```bash
python benchmarks/comparison/run.py \
  --rows 50000 \
  --seed 123 \
  --overlap-ratio 0.75 \
  --changed-ratio 0.15 \
  --duplicate-ratio 0.05
```

## Result Format

Each JSONL line is one normalized scenario result:

```json
{
  "adapter": "uniqdiff",
  "scenario": "row_presence_by_key",
  "support_level": "native",
  "status": "ok",
  "elapsed_seconds": 0.123456,
  "peak_memory_bytes": 1234567,
  "output_bytes": 0,
  "only_in_left_count": 3000,
  "only_in_right_count": 3000,
  "common_count": 7000,
  "duplicate_count": null,
  "changed_rows_count": null,
  "changed_fields_count": null,
  "notes": [],
  "error": null,
  "extra": {}
}
```

The Markdown report contains:

- workload-dependent disclaimer;
- fit-by-use-case table;
- measurement table;
- support label definitions.

If an optional dependency is missing, the adapter row is marked
`status=skipped` while retaining the scenario's intended support label. This
keeps the fit-by-use-case table useful even on a minimal development machine.

## Interpreting Results

Use the report to answer practical questions:

- Is the scenario native for this tool?
- Does the implementation require custom code?
- Does the adapter materialize full inputs in memory?
- Is large output streamed or written through a file-oriented path?
- Are missing optional dependencies being skipped cleanly?

For release notes, include the machine profile, dataset arguments, Python version,
dependency versions, and the raw JSONL file.
