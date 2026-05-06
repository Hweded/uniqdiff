# Changelog

## Unreleased

- Improved `mode="auto"` decision metadata with requested/selected disk strategy,
  chunk size, ordering, common, and duplicate flags.
- Added `disk_strategy="auto"` so the planner can choose between SQLite, hash
  partitioning, and external sort for disk-backed workloads.
- Documented the smarter auto-mode heuristic and auto disk strategy selection.
- Added `iter_sorted_diff()` for exact streaming comparison of already sorted
  inputs without temporary files.
- Added `compare_sorted_iter()` as the public engine convenience wrapper for
  sorted streaming comparison.
- Added `write_sorted_diff()` and `write_sorted_diff_file()` for direct JSONL/CSV
  output from sorted streaming comparison.
- Added a reproducible profiling suite for memory, disk, file-result, and sorted
  streaming modes, with JSONL output and Markdown reports.
- Optimized disk temporary storage with compact scalar blobs and length-prefixed
  binary temp records for hash partitioning and external sort.
- Reduced JSONL file-result overhead by avoiding per-row result dict allocation
  and fast-pathing common scalar JSON values.

## 1.0.0

- Released `uniqdiff` as a stable exact comparison engine for Python and the
  UniqTools ecosystem.
- Stabilized the public engine API: core comparison helpers, structured comparison,
  source/file comparison, result objects, lazy result readers, connector protocol,
  built-in local connectors, exact backends, file result mode, and CLI commands.
- Marked package metadata as production/stable.
- Documented the engine boundary, public/internal API boundary, result schema,
  backend behavior, known limitations, migration guidance, and backward
  compatibility policy.
- Standardized CLI `duplicates --summary` output on `duplicate_count`.
- Verified backend parity, file result schema compatibility, CLI fixture examples,
  docs index links, linting, type checking, tests, coverage, and package build.
- Added release process documentation and package metadata validation for final
  publishing preparation.
- Switched the open-source core license from MIT to Apache-2.0 and added commercial
  support, service, funding, and notice files.

## 0.9.0

- Prepared the package for the stable comparison engine foundation release.
- Updated package metadata from alpha to beta.
- Added stable engine contract for positioning `uniqdiff` as the comparison engine
  layer for the UniqTools ecosystem.
- Added final 1.0 audit documentation for public/internal module boundaries,
  release notes, supported Python versions, official optional extras, and known
  limitations.
- Expanded CLI documentation to cover all documented flags and fixture-backed smoke
  examples.
- Removed unimplemented `duckdb` and `pandas` optional extras from the official
  package metadata.

## Initial 0.x Development

- Initial MVP API.
- Added in-memory comparison for iterable data.
- Added key-based comparison for dicts, objects, and dataclasses.
- Added normalization helpers.
- Added duplicate detection and comparison statistics.
- Added CSV, JSONL, and text file readers.
- Added CLI commands for compare, diff, intersection, and duplicates.
- Added SQLite-backed disk mode for exact comparison and duplicate detection.
- Added hash partitioning disk strategy and partition-count configuration.
- Added external sort disk strategy for chunk sorting and merge comparison.
- Added file result mode for writing large disk-mode outputs to JSONL/CSV.
- Added predictable auto-mode backend selection with memory-limit metadata.
- Added stdlib benchmark runner and GitHub Actions CI workflow.
- Added Hypothesis property-based backend equivalence tests.
- Added optional fuzzy string comparison helper.
- Added Bloom filter and probabilistic diff candidate helpers.
- Added connector API with registry and built-in iterable/file connectors.
- Added CLI `--summary` output and `--fail-on-diff` CI exit-code behavior.
- Expanded backend consistency tests for key-based and connector-backed comparison.
- Expanded benchmark runner with auto scenarios, structured-row inputs, throughput,
  memory MB, output MB, and JSON report output.
- Improved `mode="auto"` metadata with item-size estimate, memory safety factor,
  effective memory limit, and selected backend.
- Added lazy result readers for JSONL/CSV file-result outputs and file-backed
  `CompareResult.iter_unique()` / `CompareResult.iter_section()`.
- Added TSV input support and gzip-aware file reading for CSV, TSV, JSONL, and text
  sources.
- Added CSV/TSV dialect options: delimiter, quote character, header control, and
  fieldnames for headerless files.
- Added optional Parquet connector and reader backed by `pyarrow` via
  `uniqdiff[parquet]`.
- Added practical recipes for CSV comparison, new/removed rows, key comparison,
  JSON/JSONL/CSV output, lazy result reading, gzip/TSV files, headerless CSV, and CI.
- Added release-readiness documentation for backend behavior, migration to 1.0,
  backward compatibility, and the 1.0 release checklist.
