# Limitations and Security

## Trusted Callables

User-provided key, normalizer, and comparator-style functions are trusted code. Do not
pass untrusted functions from users into `uniqdiff`.

## Hashing

Hashing and canonicalization are used for comparison tokens. Exact backends compare
tokens, so users should choose stable keys or canonical values for critical workflows.

## Disk Mode

Disk mode is slower than memory mode and depends on filesystem performance.

Temporary files are automatically removed, but callers should provide a safe `temp_dir`
for production jobs.

Ordering should not be treated as the primary cross-backend semantic guarantee. Use
result sections and stats for program logic instead of relying on ordering alone.

Hash partitioning and external sort need enough temporary disk space. If the
configured `disk_limit` is exceeded, the operation fails with a documented
`DiskLimitExceededError`.

## File Result Mode

File result mode writes `.jsonl` or `.csv` atomically through a temporary sibling file.
If writing fails, the final output path is not replaced.

The stable row schema is `section` and `value`. Consumers should ignore unknown future
metadata fields, but should treat row schema changes as breaking changes.

## Field Diff

Field diff indexes the second input by key. If duplicate keys appear in the second
input, the first row for that key is used for comparison and later rows are counted in
`metadata["duplicate_second_key_count"]`.

Use `columns` or `exclude_columns` to keep large row comparisons focused. Streaming
field-diff output is JSONL-only so large changed-row outputs can be consumed lazily.

## Schema Diff

Schema inference is based on observed values. It is not a database DDL parser and it
does not enforce schema validation policies.

Use `sample_size` for faster checks on large files, but treat sampled schema results
as approximate observations of the inspected rows.

## Fuzzy and Probabilistic Features

Fuzzy matching and Bloom filters are public helper APIs, but they are not part of the
exact comparison core.

Bloom filters can produce false positives. Fuzzy comparison is approximate, greedy,
and not suitable for very large all-pairs matching without additional indexing.

## Supported Python Versions

The 1.0 support window is Python 3.9 through 3.13.

## Official Optional Extras

Official 1.0 extras:

- `dev`;
- `fuzzy`;
- `parquet`.

`fuzzy` installs `rapidfuzz` for approximate string helpers. `parquet` installs
`pyarrow` for Parquet file readers and connectors. Heavy database, cloud, and
product-layer integrations are intentionally outside the core package.
