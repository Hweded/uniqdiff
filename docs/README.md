# uniqdiff Documentation

This directory contains project documentation for users and maintainers.

## Guides

- [Quick Start](quick-start.md)
- [Recipes](recipes.md)
- [Stable Engine Contract](stable-engine-contract.md)
- [Engine Boundary](engine-boundary.md)
- [UniqTools Concept](uniqtools-concept.md)
- [Public API Boundary](public-api.md)
- [API Reference](api-reference.md)
- [Connectors](connectors.md)
- [CLI](cli.md)
- [Backend Behavior](backend-behavior.md)
- [Disk Mode](disk-mode.md)
- [Hash Partitioning](hash-partitioning.md)
- [External Sort](external-sort.md)
- [File Result Mode](file-result-mode.md)
- [Result Schema](result-schema.md)
- [Auto Mode](auto-mode.md)
- [Performance](performance.md)
- [Fuzzy Comparison](fuzzy.md)
- [Bloom Filters](bloom-filters.md)
- [Property-Based Tests](property-based-tests.md)
- [Benchmarks](benchmarks.md)
- [CI/CD](ci.md)
- [Migration Guide](migration-guide.md)
- [Backward Compatibility](backward-compatibility.md)
- [Release 1.0 Checklist](release-1.0.md)
- [Release Notes 1.0](release-notes-1.0.md)
- [Release Process](release-process.md)
- [Limitations and Security](limitations-security.md)

## Project Files

- [License](../LICENSE)
- [Commercial Support](../COMMERCIAL.md)
- [Support](../SUPPORT.md)
- [Services](../SERVICES.md)

## Current Status

`uniqdiff` provides exact comparison across memory and disk-backed strategies:

- memory backend for small and medium inputs;
- SQLite backend for simple disk-backed exact comparison;
- hash partitioning backend for partition-by-partition processing;
- external sort backend for sorted chunk and merge processing;
- file result mode for large result sets.
- connector API for pluggable sources;
- fuzzy string comparison as an approximate helper outside the exact engine;
- Bloom filter candidate filtering as a probabilistic helper outside the exact engine.

## Release Readiness

The project now includes documentation for practical usage recipes, backend behavior,
migration guidance, and backward compatibility policy. These pages define the path to
a stable 1.0 release.
