# Release 1.0 Checklist

This page records what must be true for `uniqdiff` 1.0.0.

The project is now positioned as a stable exact comparison engine for the UniqTools
ecosystem. The goal of 1.0.0 is stability and a clear engine boundary, not adding
every possible data-product feature.

## 1.0 Goals

- Stable public API for memory, disk, and connector workflows.
- Documented behavior for all exact backends.
- Clear large-data story with disk mode and file result mode.
- Practical documentation for common CSV/JSONL/TSV/Parquet tasks.
- Reliable CLI behavior for scripts and CI/CD.
- Backward compatibility policy.
- Migration guide from early 0.x usage.
- Stable engine contract for downstream tools.

## Stable API Surface

The 1.0 API includes:

- comparison helpers: `compare`, `diff`, `unique`, `intersection`, `duplicates`;
- structured helpers: `compare_by_key`, `compare_by_hash`;
- source helpers: `compare_iter`, `compare_files`, `compare_streams`, `compare_sources`;
- duplicate helpers: `duplicates_source`;
- result helpers: `CompareResult`, `CompareStats`, lazy result readers;
- connector protocol, built-in connectors, and registry helpers;
- CLI commands: `compare`, `diff`, `intersection`, `duplicates`.

The 1.0 API does not include product-layer features such as reports, workflow
runners, dashboards, schema validation, data quality rules, SaaS logic, or enterprise
connector management.

## Backend Requirements

Each stable backend has:

- documented behavior;
- tests against common semantic expectations;
- tests for empty input;
- tests for duplicate handling;
- tests for key-based comparison;
- tests for file-backed output where supported;
- documented ordering guarantees or non-guarantees.

## Documentation Requirements

1.0 documentation includes:

- quick start;
- API reference;
- recipes;
- backend behavior;
- connector guide;
- disk-mode guide;
- file-result-mode guide;
- result schema guide;
- engine boundary guide;
- auto-mode guide;
- performance and benchmark guide;
- CLI guide;
- migration guide;
- backward compatibility policy;
- limitations and security notes.

## Release Checklist

- [x] `ruff` passes.
- [x] `mypy` passes.
- [x] `pytest` passes.
- [x] Test coverage is at least 85%.
- [x] `python -m build --sdist --wheel` passes.
- [x] README describes installation, quick start, files, connectors, disk mode, CLI, and limitations.
- [x] Changelog is updated.
- [x] Public API is reviewed for accidental exports.
- [x] Backend behavior docs are reviewed.
- [x] Migration guide is reviewed.
- [x] Backward compatibility policy is reviewed.
- [x] Optional dependencies are documented.
- [x] CLI exit codes are documented.
- [x] Stable engine contract is documented.
- [x] Engine boundary is documented.
- [x] Result schema is documented.
- [x] Non-scope is documented to prevent product logic from entering the engine package.
- [x] Public modules are explicitly separated from internal modules.
- [x] Documented CLI flags are covered by `docs/cli.md`.
- [x] CLI examples are smoke-tested against repository fixture files.
- [x] Backend equivalence tests cover memory, SQLite, hash partitioning, external sort,
  and auto mode.
- [x] File result row schema is covered by backward-compatibility tests.
- [x] 1.0 release notes exist.
- [x] Known limitations are documented.
- [x] Supported Python versions are declared.
- [x] Official optional extras for 1.0 are declared.

## Known 1.0 Non-Goals

These can remain future work if documented:

- distributed processing;
- full SQL engine semantics;
- fuzzy matching at very large scale without indexing;
- guaranteed identical ordering across all disk backends;
- automatic schema inference beyond documented file readers;
- all possible enterprise storage connectors in the core package.

## Post-1.0 Development

After 1.0, prefer minor releases for additive features:

- new optional connectors;
- row-level diff;
- richer storage backends;
- improved auto-mode heuristics;
- more benchmark scenarios;
- integration recipes for Airflow, Dagster, dbt, FastAPI, and CI/CD.
