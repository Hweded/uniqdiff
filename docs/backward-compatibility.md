# Backward Compatibility Policy

This policy defines how `uniqdiff` should evolve after 1.0.

## Stable Public API

The following APIs are considered stable for 1.x:

- `compare`;
- `diff`;
- `unique`;
- `intersection`;
- `duplicates`;
- `compare_by_key`;
- `compare_by_hash`;
- `compare_iter`;
- `compare_files`;
- `compare_streams`;
- `compare_sources`;
- `duplicates_source`;
- `CompareResult`;
- `CompareStats`;
- connector protocol and registry helpers;
- built-in file connectors;
- `iter_result_rows`;
- `iter_result_values`;
- `iter_compare_events`;
- `iter_event_rows`;
- `summarize_events`;
- `summarize_event_file`;
- `compare_fields`;
- `compare_file_fields`;
- `compare_fields_sorted`;
- `compare_file_fields_sorted`;
- `infer_schema`;
- `compare_schema`;
- `compare_file_schema`;
- `uniqdiff.engine` facade exports;
- documented CLI commands and flags.

Stable means:

- function names remain available;
- documented parameters are not removed in minor releases;
- documented return fields remain available;
- behavior changes are documented and tested.

## Semantic Versioning

`uniqdiff` follows semantic versioning after 1.0:

- patch releases fix bugs and documentation;
- minor releases add backward-compatible features;
- major releases may include breaking changes.

## Allowed Minor-Release Changes

Minor releases may add:

- new optional connectors;
- new output formats;
- new backend strategies;
- new metadata fields;
- new CLI flags;
- new optional dependencies;
- performance improvements that preserve exact comparison semantics.

## Breaking Changes

Breaking changes require a major version unless there is a severe security or data
corruption issue.

Examples:

- removing a public function;
- changing default comparison semantics;
- changing result field names;
- changing CLI exit-code meaning;
- removing a backend strategy;
- changing file result row schema.

## Deprecation Policy

When possible, breaking changes should follow this path:

1. Add the replacement API.
2. Document the old API as deprecated.
3. Emit a warning when practical.
4. Keep the deprecated API for at least one minor release.
5. Remove it only in the next major release.

## Metadata Compatibility

`metadata` may receive new fields in minor releases.

Users should:

- treat unknown metadata fields as informational;
- avoid depending on undocumented internal fields;
- use documented stats fields for program logic.

## Optional Dependency Compatibility

Official 1.1 optional extras are `dev`, `benchmark`, `fuzzy`, and `parquet`.
Future optional connectors may evolve independently when they are added and
documented.

If an optional dependency is missing, `uniqdiff` should raise a clear
`MissingOptionalDependencyError` or another documented `UniqDiffError` subclass.

## CLI Compatibility

CLI compatibility covers:

- command names;
- documented flags;
- output schema for JSON summary and file result rows;
- exit codes.

Stable summary counters:

- comparison summaries use `duplicate_first_count` and `duplicate_second_count`;
- single-source `duplicates --summary` uses `duplicate_count`.

Exit code contract:

- `0`: command completed successfully;
- `1`: differences or duplicates were found with `--fail-on-diff`;
- `2`: invalid input, missing file, unsupported format, corrupted data, or option error.
