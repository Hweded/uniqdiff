# CLI

`uniqdiff` provides a small command line interface for scripts and CI/CD jobs.

## Full Result

```bash
uniqdiff compare old.csv new.csv --format csv --key id
uniqdiff compare old.tsv new.tsv --format tsv --key id
uniqdiff compare old.csv.gz new.csv.gz --format auto --key id
uniqdiff compare old.parquet new.parquet --format parquet --columns id,name --key id
uniqdiff diff old.txt new.txt --format txt
uniqdiff intersection old.jsonl new.jsonl --format jsonl --key id
uniqdiff duplicates users.csv --format csv --key email
```

Commands:

- `uniqdiff compare FILE_A FILE_B`: full comparison, including `common` by default;
- `uniqdiff diff FILE_A FILE_B`: differences only;
- `uniqdiff intersection FILE_A FILE_B`: values found in both files;
- `uniqdiff duplicates FILE_A`: duplicates inside one file.

Input flags:

- `--format auto|csv|tsv|jsonl|parquet|txt`;
- `--input-format auto|csv|tsv|jsonl|parquet|txt` when `--format` is used for output;
- `--encoding utf-8`;
- `--key id` or `--key id,tenant`;
- `--delimiter ","`;
- `--quotechar "\"`;
- `--no-header`;
- `--fieldnames id,name`;
- `--columns id,name`;
- `--parquet-batch-size 65536`.

CSV/TSV dialect options:

```bash
uniqdiff compare old.csv new.csv --format csv --delimiter ";" --key id
uniqdiff compare old.csv new.csv --format csv --no-header --fieldnames id,name --key id
```

Parquet support requires the optional extra:

```bash
pip install "uniqdiff[parquet]"
```

Backend flags:

- `--mode memory|disk|auto`;
- `--chunk-size 100000`;
- `--memory-limit 512MB` for `compare`, `diff`, and `intersection`;
- `--temp-dir ./tmp`;
- `--disk-limit 10GB`;
- `--disk-strategy sqlite|hash-partition|hash_partition|external-sort|external_sort`;
- `--partition-count 128`.

Output and behavior flags:

- `--format jsonl` for the `uniqdiff.jsonl` machine-readable event stream in
  `compare` and `diff`;
- `--result-mode memory|file` for `compare`, `diff`, and `intersection`;
- `--output path.json|path.jsonl|path.csv` for `compare`, `diff`, and `intersection`;
- `--include-duplicates` for comparison commands;
- `--field-diff` for field-level changes between rows with the same `--key`;
- `--exclude-columns name,updated_at` for `--field-diff`;
- `--max-rows 1000` for limiting emitted field-diff rows;
- `--max-bytes 10MB` for limiting streamed field-diff JSONL output;
- `--sorted-input` for low-memory field diff when both inputs are already sorted
  by `--key`;
- `--schema-diff` for inferred column/type/nullability changes;
- `--schema-sample-size 10000` for limiting schema inference rows;
- `--empty-string-not-null` for treating empty strings as string values in schema inference;
- `--loose-numeric-types` for treating `int` and `float` as a shared `number` type;
- `--summary`;
- `--fail-on-diff`;
- `--lower`;
- `--strip`;
- `--no-strip`;
- `--remove-spaces`;
- `--remove-special`.

`duplicates` intentionally does not expose `--memory-limit`, `--result-mode`, or
`--output` in 1.0. It returns a JSON list or compact summary to stdout.

## Summary Mode

Use `--summary` when a pipeline only needs counters and backend metadata:

```bash
uniqdiff compare old.csv new.csv --format csv --key id --summary
```

The output contains counts such as:

- `only_in_first_count`;
- `only_in_second_count`;
- `common_count`;
- `duplicate_first_count`;
- `duplicate_second_count`;
- `backend`;
- `result_mode`.

`duplicates` also supports `--summary`; it returns `duplicate_count` and `empty`.

## CI Exit Codes

By default, successful commands return `0` even when differences are found.

Use `--fail-on-diff` when differences should fail a CI job:

```bash
uniqdiff diff old.csv new.csv --format csv --key id --summary --fail-on-diff
```

Exit codes:

- `0`: command completed successfully;
- `1`: differences or duplicates were found with `--fail-on-diff`;
- `2`: invalid input, missing file, unsupported format, corrupted data, or option error.

## Large Outputs

The primary machine-readable output is the `uniqdiff.jsonl` event stream:

```bash
uniqdiff compare old.csv new.csv \
  --key id \
  --format jsonl \
  --output diff.jsonl
```

Each line is one JSON object. The first event is `metadata`, the last event is
`summary`, and every event has a required `type` field.

If input extensions are ambiguous, set the input format separately:

```bash
uniqdiff compare old_snapshot new_snapshot \
  --input-format csv \
  --key id \
  --format jsonl
```

The older `result_mode="file"` contract remains available when you need raw
`section`/`value` rows:

```bash
uniqdiff compare old.csv new.csv \
  --format csv \
  --key id \
  --mode disk \
  --result-mode file \
  --output diff.jsonl
```

File result mode applies to `compare`, `diff`, and `intersection`. The `duplicates`
command returns JSON to stdout and can be reduced with `--summary`.

## Field-Level Diff

Use `--field-diff` when both inputs contain rows with stable keys and you need to
know which fields changed inside matching rows:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --field-diff \
  --columns name,status,email \
  --summary
```

Field-level diff is an engine feature, not a report generator. It emits rows with
this JSON shape:

```json
{"key":"123","changes":[{"field":"status","left":"draft","right":"active"}]}
```

For large outputs, write changed rows directly to JSONL:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --field-diff \
  --exclude-columns updated_at,loaded_at \
  --max-rows 100000 \
  --max-bytes 100MB \
  --output changed-fields.jsonl \
  --summary
```

`--summary` returns counters and `summary_by_column`, which is useful in CI/CD
when the full changed-row output is too large.

Field diff can also be emitted as `uniqdiff.jsonl` events:

```bash
uniqdiff diff old.csv new.csv \
  --key id \
  --field-diff \
  --columns name,status \
  --format jsonl \
  --output changed-events.jsonl
```

When both files are already sorted by the same key, use `--sorted-input` to stream
matching-key field changes without building an index of the second file:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --field-diff \
  --sorted-input \
  --columns name,status \
  --summary
```

`--sorted-input` validates non-descending key order while reading. It reports
changed-row and changed-field counters, but it does not materialize full
left/right/common row counts because it is designed for bounded-memory field
change streaming.

Field-diff CLI constraints:

- `--field-diff` requires `--key`;
- `--field-diff` cannot be combined with `--schema-diff`;
- `--field-diff --output` supports only `.jsonl`;
- `--sorted-input` requires both inputs to be sorted by the same `--key` and
  normalization settings;
- `--result-mode` is not used with `--field-diff`.

## Schema Diff

Use `--schema-diff` when you need an engine-level check for structural changes:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --schema-diff \
  --summary \
  --fail-on-diff
```

Schema diff reports:

- added columns;
- removed columns;
- changed inferred value types;
- changed nullability.

By default, empty strings count as null-like values for schema inference. Use
`--empty-string-not-null` when empty strings should remain ordinary string
values. By default, `int` and `float` are distinct inferred types. Use
`--loose-numeric-types` when both should be treated as `number`. For very large
files, use `--schema-sample-size` to inspect only the first N rows per input.

Schema-diff CLI constraints:

- `--schema-diff` cannot be combined with `--field-diff`;
- `--schema-diff --output` supports only `.json` unless `--format jsonl` is used
  for event output;
- `--result-mode` is not used with `--schema-diff`.

## Fixture Smoke Examples

The repository keeps small fixture files under `tests/fixtures` so CLI examples can be
verified in tests:

```bash
uniqdiff compare tests/fixtures/left.csv tests/fixtures/right.csv --format csv --key id --summary
uniqdiff compare tests/fixtures/left.tsv tests/fixtures/right.tsv --format tsv --key id
uniqdiff diff tests/fixtures/left.txt tests/fixtures/right.txt --format txt --output diff.json
uniqdiff diff tests/fixtures/left.csv tests/fixtures/right.csv --format csv --key id --field-diff --columns name --summary
uniqdiff diff tests/fixtures/left.csv tests/fixtures/right.csv --format csv --key id --field-diff --sorted-input --columns name --summary
uniqdiff diff tests/fixtures/left.csv tests/fixtures/right.csv --format csv --schema-diff --summary
uniqdiff compare tests/fixtures/left.csv tests/fixtures/right.csv --key id --format jsonl
uniqdiff intersection tests/fixtures/left.jsonl tests/fixtures/right.jsonl --format jsonl --key id
uniqdiff duplicates tests/fixtures/dupes.txt --format txt --summary --fail-on-diff
```
