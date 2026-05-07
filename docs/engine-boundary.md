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
- engine-level field diff by key;
- engine-level schema inference and schema diff;
- the connector protocol and built-in local connectors;
- a direct CLI for engine-level comparison tasks.

## Non-Responsibilities

`uniqdiff` should not own:

- HTML, PDF, Excel, or business reports;
- schema validation policies and rule sets;
- data quality rule engines;
- data cleaning workflows;
- YAML workflow runners;
- dashboards or UI templates;
- SaaS, billing, user, team, or project management;
- enterprise connector management;
- heavy cloud/database integrations in the core package.

These belong in higher-level packages such as `uniqreport`, `uniqschema`,
`uniqcheck`, `uniqrowdiff`, and `uniqtools-cli`. `uniqdiff` may expose primitive
field/schema facts, but product workflows, reports, policies, and user-facing
templates stay outside the engine.

## Public Extension Points

Downstream packages should extend `uniqdiff` through:

- the explicit `uniqdiff.engine` facade for stable engine primitives;
- root package exports for backward-compatible existing integrations;
- documented connector protocol;
- documented result objects;
- documented lazy result readers;
- documented CLI contracts for automation.

They should not import internal backend modules directly.

Use `uniqdiff.engine` when building another library or product layer:

```python
from uniqdiff.engine import compare_files, iter_result_rows
```

The root `uniqdiff` package remains supported. The engine facade exists to make the
architecture boundary clearer for downstream packages such as `uniqrowdiff`,
`uniqschema`, `uniqcheck`, and `uniqtools-cli`.

## Internal Engine Layers

The internal engine is intentionally split into small layers:

- `core`: public API orchestration and result assembly;
- `tokens`: key extraction, normalizer application, and canonical token creation;
- `planner`: mode normalization, auto-mode decision metadata, and backend selection;
- `storage`: memory and disk-backed exact comparison backends;
- `connectors`: source adapters and the connector registry;
- `output`: file result writing and lazy result readers;
- `fields` and `schema`: engine-level structured diff primitives.

Only documented public APIs are covered by the compatibility contract. These internal
modules exist to keep the engine maintainable and may evolve between minor releases.

## Compatibility Rule

The 1.0 compatibility contract covers documented engine APIs, result schemas, CLI
behavior, and connector protocol. It does not cover internal module layout, temporary
storage internals, or private helper functions.
