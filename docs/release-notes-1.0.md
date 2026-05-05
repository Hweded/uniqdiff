# Release Notes 1.0.0

`uniqdiff` 1.0.0 establishes the package as a stable exact comparison engine for
Python projects and the UniqTools ecosystem.

Package metadata is marked as production/stable for this release.

The open-source core is licensed under the Apache License 2.0.

## Highlights

- Stable exact comparison helpers for iterables, structured records, files, streams,
  and connector-backed sources.
- Stable result objects: `CompareResult` and `CompareStats`.
- Memory, SQLite, hash partitioning, external sort, and auto backend modes.
  `hash_partition`, `external_sort`, and `auto` are stable 1.0 APIs documented as
  advanced modes because they expose additional operational trade-offs.
- File result mode for large JSONL/CSV diff outputs.
- Lazy result readers for file-backed outputs.
- Connector protocol with built-in local connectors for iterable, file, CSV, TSV,
  JSONL, TXT, gzip-compressed local files, and optional Parquet.
- CLI commands for `compare`, `diff`, `intersection`, and `duplicates`.
- Documented compatibility policy, migration guide, backend behavior, engine boundary,
  public API boundary, result schema, known limitations, and release checklist.
- Commercial support, support policy, service information, and funding metadata are
  documented outside the core engine implementation.

## Stable Engine API

The stable engine API is the root package facade:

- `compare`, `diff`, `unique`, `intersection`, `duplicates`;
- `compare_by_key`, `compare_by_hash`;
- `compare_iter`, `compare_streams`, `compare_files`, `compare_sources`;
- `duplicates_source`;
- `CompareResult`, `CompareStats`;
- `iter_result_rows`, `iter_result_values`;
- connector protocol, registry helpers, and built-in local connectors;
- documented exceptions.

Internal backend modules remain implementation details.

## Engine Boundary

`uniqdiff` 1.0 is an engine package. It owns exact comparison semantics, local source
connectors, result schemas, backend selection, and a direct CLI. Reports, workflow
runners, schema validation, data quality rules, dashboards, cloud connector
management, and SaaS logic belong in higher-level packages.

## Supported Python Versions

`uniqdiff` 1.0 supports Python 3.9 through 3.13.

The package uses `requires-python = ">=3.9"` and ships type information through
`py.typed`.

## Official Optional Extras

Officially supported 1.0 extras:

- `uniqdiff[dev]`: development, linting, type checking, testing, and build tooling;
- `uniqdiff[fuzzy]`: optional `rapidfuzz` acceleration for approximate string helper
  APIs;
- `uniqdiff[parquet]`: optional `pyarrow` support for Parquet readers and connectors.

Heavy database, cloud, and product-layer integrations are intentionally not part of
the core 1.0 package.

## File Result Schema

JSONL result files contain one JSON object per line:

```json
{"section": "only_in_first", "value": {"id": "1"}}
```

CSV result files contain the header:

```text
section,value
```

The stable columns are `section` and `value`. New sections may be added only as
documented backward-compatible extensions. The single-source `duplicates --summary`
counter is `duplicate_count`; `CompareStats` uses `duplicate_first_count` and
`duplicate_second_count`.

## Known Limitations

- Disk backends are slower than memory mode.
- Exact semantics depend on stable comparison tokens produced by key extraction,
  normalization, and canonicalization.
- Hash partitioning and external sort use temporary files and depend on filesystem
  performance and available disk space.
- Ordering should not be treated as the primary cross-backend semantic guarantee.
- Bloom filters can produce false positives; in candidate-diff workflows this can
  hide true differences.
- Fuzzy comparison is approximate, greedy, and not suitable for very large all-pairs
  matching without additional indexing.
- User-provided key and normalizer callables are trusted code.

## Upgrade Notes

Early 0.x users should import stable APIs from `uniqdiff` instead of internal modules,
review file result mode behavior, and check the migration guide before pinning to
1.0.
