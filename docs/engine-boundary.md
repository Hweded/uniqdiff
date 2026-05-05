# Engine Boundary

`uniqdiff` is a stable comparison engine, not a data product platform.

The engine boundary exists so other UniqTools packages can safely depend on
`uniqdiff` without inheriting reporting, workflow, SaaS, or enterprise-management
logic.

## Responsibilities

`uniqdiff` owns:

- exact comparison semantics;
- token extraction through `key` and `normalizer`;
- core helpers such as `compare`, `diff`, `unique`, `intersection`, and `duplicates`;
- structured comparison helpers such as `compare_by_key` and `compare_by_hash`;
- source helpers such as `compare_iter`, `compare_streams`, `compare_files`,
  `compare_sources`, and `duplicates_source`;
- memory, SQLite, hash partitioning, external sort, and auto backend selection;
- memory and file result modes;
- stable result objects and lazy result readers;
- the connector protocol and built-in local connectors;
- a direct CLI for engine-level comparison tasks.

## Non-Responsibilities

`uniqdiff` should not own:

- HTML, PDF, Excel, or business reports;
- schema validation;
- data quality rule engines;
- data cleaning workflows;
- YAML workflow runners;
- dashboards or UI templates;
- SaaS, billing, user, team, or project management;
- enterprise connector management;
- heavy cloud/database integrations in the core package.

These belong in higher-level packages such as `uniqreport`, `uniqschema`,
`uniqcheck`, `uniqrowdiff`, and `uniqtools-cli`.

## Public Extension Points

Downstream packages should extend `uniqdiff` through:

- root package exports;
- documented connector protocol;
- documented result objects;
- documented lazy result readers;
- documented CLI contracts for automation.

They should not import internal backend modules directly.

## Compatibility Rule

The 1.0 compatibility contract covers documented engine APIs, result schemas, CLI
behavior, and connector protocol. It does not cover internal module layout, temporary
storage internals, or private helper functions.
