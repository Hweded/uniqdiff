# Stable Engine Contract

This document fixes `uniqdiff` as the stable comparison engine for the UniqTools
ecosystem.

`uniqdiff` is not intended to contain all product logic. It provides the exact
comparison layer that other tools can safely build on top of.

## Ecosystem Role

`uniqdiff` is the engine layer for:

- `uniqprofile`;
- `uniqschema`;
- `uniqcheck`;
- `uniqreport`;
- `uniqrowdiff`;
- `uniqtools-cli`.

These tools should depend on `uniqdiff` for exact comparison semantics instead of
duplicating comparison logic.

## 1.0 Scope

The 1.0 release should stabilize the following public API and behavior.

### Core Comparison Helpers

- `compare`;
- `diff`;
- `unique`;
- `intersection`;
- `duplicates`.

These helpers define exact comparison semantics and should remain the primary API for
simple iterable workflows.

### Structured Comparison

- `compare_by_key`;
- `compare_by_hash`.

These helpers define stable structured comparison behavior using keys, compound keys,
callable keys, normalizers, and canonicalized values.

### Source Comparison

- `compare_iter`;
- `compare_streams`;
- `compare_files`;
- `compare_sources`;
- `duplicates_source`.

These helpers define how external sources enter the engine without adding product
logic to the core package.

### Result Objects

- `CompareResult`;
- `CompareStats`.

These objects are the stable result contract for downstream tools.

Stable fields:

- `only_in_first`;
- `only_in_second`;
- `common`;
- `unique`;
- `duplicates_first`;
- `duplicates_second`;
- `stats`;
- `metadata`;
- `warnings`.

### Lazy Result Readers

- `iter_result_rows`;
- `iter_result_values`;
- `CompareResult.iter_unique`;
- `CompareResult.iter_section`.

These APIs allow large result files to be consumed without loading them fully into
memory.

### Connector Protocol

Every connector implements:

- `name`;
- `open()`;
- `describe()`.

This protocol should stay small. Complex connector management belongs outside
`uniqdiff`.

### Built-In Local Connectors

Stable built-ins:

- `iterable`;
- `file`;
- `csv`;
- `tsv`;
- `jsonl`;
- `parquet` as optional;
- `txt`;
- gzip local files.

Connector aliases such as `tab`, `pq`, and `text` are convenience aliases and should
remain documented if kept in 1.0.

### Backends

Stable exact backends:

- `memory`;
- `sqlite`;
- `hash_partition`;
- `external_sort`;
- `auto`.

`hash_partition`, `external_sort`, and `auto` are stable 1.0 APIs, but they are
documented as advanced modes because they expose additional operational trade-offs
around temporary files, partition counts, sorting passes, and backend-selection
metadata.

Auto-mode decisions are produced by the internal planner layer and exposed through
`metadata["auto_decision"]`. The metadata is stable enough for diagnostics, but
callers should treat unknown future fields as informational.

Backend semantics should agree on exact comparison meaning. Ordering may differ
between disk strategies and should not be treated as a cross-backend guarantee.

### Result Modes

Stable result modes:

- `memory`;
- `file`.

`result_mode="file"` is the engine-level path for large diff output.

### CLI

Stable CLI commands:

- `uniqdiff compare`;
- `uniqdiff diff`;
- `uniqdiff intersection`;
- `uniqdiff duplicates`.

The CLI is a direct engine CLI. It should not become a workflow runner. Cross-tool
orchestration belongs in `uniqtools-cli`.

### Stats And Metadata

`uniqdiff` should expose enough metadata for downstream tools to understand:

- selected backend;
- disk strategy;
- chunk size;
- result mode;
- connector descriptions;
- output path;
- auto-mode decision metadata.

New metadata fields may be added in minor releases. Downstream tools should treat
unknown metadata as informational.

## Explicit Non-Scope

The following must not be added to `uniqdiff` core:

- HTML/PDF/Excel reports;
- business reports;
- data cleaning;
- schema validation;
- workflow YAML runner;
- full data quality rule engine;
- dashboards;
- SaaS logic;
- enterprise/cloud connector management;
- complex UI/report templates;
- payment/licensing logic;
- user/team/project management;
- heavy database/cloud dependencies in core.

These belong in higher-level UniqTools packages.

## Current Status

The current codebase already includes:

- memory backend;
- SQLite disk backend;
- hash partition backend;
- external sort backend;
- auto mode;
- file result mode;
- lazy result readers;
- connector registry;
- local file connectors;
- TSV and gzip support;
- optional Parquet support;
- CLI;
- documentation;
- migration guide;
- backward compatibility policy;
- tests;
- type checking;
- linting;
- build checks.

Therefore, `uniqdiff` should be treated as a stable 1.0 exact comparison engine, not
an early exploratory project.

## 1.0 Release Principle

The 1.0 release should be framed as:

> `uniqdiff` is a stable exact comparison engine for Python and the UniqTools
> ecosystem.

It should not be framed as:

> `uniqdiff` is a complete data platform.

This distinction protects the package from scope creep and gives downstream tools a
stable base to build on.
