# Migration Guide

This guide describes how users should move from pre-1.0 versions to the stable 1.0
API.

## From Early 0.x Code To 1.0

Prefer the stable entry points:

```python
from uniqdiff import compare, compare_files, compare_sources
```

Avoid importing internal modules directly:

```python
# Avoid this in application code.
from uniqdiff.storage.sqlite import compare_sqlite
```

Use public options instead:

```python
result = compare(
    rows_a,
    rows_b,
    key="id",
    mode="disk",
    disk_strategy="sqlite",
)
```

## File Comparison

Use `compare_files()` for local files:

```python
result = compare_files("old.csv", "new.csv", format="csv", key="id")
```

Use `compare_sources()` when you need connector options or non-file sources:

```python
result = compare_sources(
    "old.csv",
    "new.csv",
    first_options={"format": "csv", "delimiter": ";"},
    second_options={"format": "csv", "delimiter": ";"},
    key="id",
)
```

## Large Results

For large outputs, migrate from in-memory result lists to file result mode:

```python
result = compare_files(
    "old.csv",
    "new.csv",
    format="csv",
    key="id",
    mode="disk",
    result_mode="file",
    output="diff.jsonl",
)
```

Then read results lazily:

```python
from uniqdiff import iter_result_values

for row in iter_result_values("diff.jsonl", sections=("only_in_second",)):
    process(row)
```

## Backend Selection

Before 1.0, users may have hardcoded disk behavior manually. For 1.0:

- use `mode="memory"` when inputs fit RAM;
- use `mode="disk"` when you explicitly want disk-backed processing;
- use `mode="auto"` when you want documented heuristics;
- use `result.metadata["auto_decision"]` to inspect auto-mode behavior.

## Connectors

Custom connectors should implement:

```python
class MyConnector:
    name = "my_source"

    def open(self):
        yield from rows

    def describe(self):
        return {"connector": self.name}
```

Register with:

```python
from uniqdiff import register_connector

register_connector("my_source", MyConnector)
```

## Optional Formats

Parquet is optional:

```bash
pip install "uniqdiff[parquet]"
```

Without the extra, Parquet operations raise a clear optional-dependency error.

## Migration Checklist

- Use public imports from `uniqdiff`.
- Use `key` for structured rows.
- Use `compare_files()` for local files.
- Use `compare_sources()` for connector-based workflows.
- Use `result_mode="file"` for large outputs.
- Use lazy result readers for large JSONL/CSV result files.
- Avoid depending on internal backend modules.
- Review backend ordering assumptions.
