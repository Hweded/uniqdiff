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

## Workload Profiles

The suite now uses concrete, deterministic CSV workloads instead of tiny toy
rows. The default profile is `orders`.

| Profile | Shape | Best for |
| --- | --- | --- |
| `orders` | Mixed order-like columns: ids, account, region, status, money, date, email, nullable note, payload. | General comparison numbers. |
| `wide_orders` | `orders` plus 20 metric columns by default. | Row width and field-diff overhead. |
| `large_output` | Lower overlap, larger payload, more only-left/only-right rows. | File/stream output behavior. |

Every run writes `metadata.json` with:

- exact workload parameters;
- schema columns and compared columns;
- expected counts for presence, duplicates, and changed fields.

The report marks whether each adapter matched the expected counts where that
scenario returns comparable counts.

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

Run a more realistic wide workload:

```bash
python benchmarks/comparison/run.py --profile wide_orders --rows 50000
```

Stress large output paths:

```bash
python benchmarks/comparison/run.py \
  --profile large_output \
  --rows 100000 \
  --scenario large_output_handling
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
- `--profile`
- `--overlap-ratio`
- `--changed-ratio`
- `--duplicate-ratio`
- `--null-ratio`
- `--payload-bytes`
- `--wide-columns`

Example:

```bash
python benchmarks/comparison/run.py \
  --rows 50000 \
  --profile orders \
  --seed 123 \
  --overlap-ratio 0.75 \
  --changed-ratio 0.15 \
  --duplicate-ratio 0.05 \
  --null-ratio 0.02 \
  --payload-bytes 64 \
  --wide-columns 8
```

## Result Format

Each JSONL line is one normalized scenario result:

```json
{
  "adapter": "uniqdiff",
  "scenario": "row_presence_by_key",
  "support_level": "native",
  "status": "ok",
  "workload": {
    "profile": "orders",
    "rows_per_side": 10000,
    "seed": 42,
    "overlap_ratio": 0.7,
    "changed_ratio": 0.2,
    "duplicate_ratio": 0.05,
    "null_ratio": 0.03,
    "payload_bytes": 24,
    "wide_columns": 0,
    "schema_columns": 11
  },
  "input_rows": 20000,
  "elapsed_seconds": 0.123456,
  "peak_memory_bytes": 1234567,
  "rows_per_second": 162000.12,
  "output_bytes": 0,
  "only_in_left_count": 3000,
  "only_in_right_count": 3000,
  "common_count": 7000,
  "duplicate_count": null,
  "changed_rows_count": null,
  "changed_fields_count": null,
  "notes": [],
  "error": null,
  "extra": {
    "expected_counts": {
      "only_in_left": 3000,
      "only_in_right": 3000,
      "common": 7000
    },
    "matches_expected": true
  }
}
```

The Markdown report contains:

- workload-dependent disclaimer;
- workload settings;
- fit-by-use-case table;
- measurement table;
- expected-count match status;
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
- Did the adapter match the deterministic expected counts?
- Are missing optional dependencies being skipped cleanly?

For release notes, include the machine profile, dataset arguments, Python version,
dependency versions, and the raw JSONL file.
