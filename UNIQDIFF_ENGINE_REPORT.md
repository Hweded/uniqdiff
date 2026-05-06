# uniqdiff Engine Report

This document summarizes the current engine scope of `uniqdiff` and the boundary
between the open-source comparison engine and higher-level UniqTools products.

## Current Role

`uniqdiff` is a stable comparison engine for local files, iterables, streams, and
connector-backed sources.

It is responsible for:

- exact comparison semantics;
- key extraction and normalization;
- row presence diff: `only_in_first`, `only_in_second`, `common`, and `unique`;
- duplicate detection;
- field-level diff for rows that share the same key;
- schema-aware diff for inferred columns, value types, and nullability;
- memory, SQLite, hash partition, external sort, and auto backends;
- memory and file result modes;
- lazy result readers;
- connector protocol and built-in local connectors;
- a direct CLI for scripts and CI/CD.

`uniqdiff` should stay focused on engine behavior. It should not become a reporting
platform, workflow runner, SaaS layer, or full data quality product.

## Public Engine Surface

Stable 1.x API groups:

- core helpers: `compare`, `diff`, `unique`, `intersection`, `duplicates`;
- structured helpers: `compare_by_key`, `compare_by_hash`;
- source helpers: `compare_iter`, `compare_streams`, `compare_files`,
  `compare_sources`, `duplicates_source`;
- sorted streaming helpers: `iter_sorted_diff`, `compare_sorted_iter`,
  `write_sorted_diff`, `write_sorted_diff_file`;
- field diff helpers: `compare_fields`, `compare_fields_files`,
  `compare_file_fields`, `iter_field_diff_rows`;
- schema helpers: `infer_schema`, `compare_schema`, `compare_file_schema`;
- result objects: `CompareResult`, `CompareStats`, `FieldDiffResult`,
  `FieldDiffStats`, `SchemaResult`, `SchemaDiffResult`;
- lazy readers: `iter_result_rows`, `iter_result_values`,
  `CompareResult.iter_unique`, `CompareResult.iter_section`.

## Backends

Supported exact comparison backends:

- `memory`: fastest path when inputs and outputs fit in RAM;
- `sqlite`: disk-backed comparison with standard-library SQLite;
- `hash_partition`: advanced disk strategy that compares hash partitions;
- `external_sort`: advanced disk strategy that sorts chunks and merges token
  streams;
- `auto`: planner-driven mode selection with diagnostic metadata.

Ordering is not the primary cross-backend contract. Consumers should rely on
sections, keys, result schemas, and stats rather than assuming identical ordering
across all disk strategies.

## Result Contracts

Primary result contracts:

- `CompareResult` / `CompareStats` for exact presence diff;
- file result rows with stable `section` and `value` fields;
- field-diff JSONL rows with stable `key` and `changes` fields;
- schema diff objects with added/removed columns, type changes, nullable changes,
  and inferred left/right schemas.

Minor releases may add metadata and warning fields. Renaming stable fields or
changing their meaning is a compatibility-affecting change.

## Engine Boundary

Keep inside `uniqdiff`:

- exact comparison;
- field/schema diff primitives;
- local file reading;
- local connectors;
- low-memory and disk-backed execution;
- CLI commands that map directly to engine operations.

Keep outside `uniqdiff`:

- HTML/PDF/Excel reports;
- business reports;
- data cleaning workflows;
- schema validation policies;
- data quality rule engines;
- YAML workflow runners;
- dashboards and UI templates;
- SaaS, billing, user, team, or project management;
- enterprise/cloud connector management;
- heavy database/cloud dependencies in the core package.

These belong in UniqTools packages such as `uniqreport`, `uniqcheck`,
`uniqtools-cli`, `uniqprofile`, `uniqschema`, and optional connector packages.

## Current Readiness

The project currently includes:

- documented public/internal API boundary;
- backend behavior documentation;
- result schema documentation;
- CLI documentation and smoke tests;
- backend parity tests;
- field diff and schema diff tests;
- linting, type checking, and package build checks;
- benchmark and profiling suites;
- Apache-2.0 license and commercial support documents.

`uniqdiff` should now be treated as a released 1.x engine foundation with ongoing
1.1 development, not as an early exploratory project.
