# Connectors

Connectors are a small extension layer for pluggable input sources.

Every connector implements:

- `open() -> Iterator[Any]`;
- `describe() -> dict[str, Any]`;
- `name`.

## Built-In Connectors

- `iterable`: already parsed Python iterable;
- `file`: auto-detected local file;
- `csv`: CSV rows as dictionaries;
- `tsv` / `tab`: TSV rows as dictionaries;
- `jsonl`: JSON Lines values;
- `parquet` / `pq`: Parquet rows as dictionaries with optional `pyarrow`;
- `txt` / `text`: text lines.

Local file connectors support plain files and gzip-compressed files with a `.gz`
suffix, for example `.csv.gz`, `.tsv.gz`, `.jsonl.gz`, and `.txt.gz`.

## Usage

```python
from uniqdiff import compare_sources

result = compare_sources(
    "old.csv",
    "new.csv",
    first_kind="csv",
    second_kind="csv",
    key="id",
)
```

TSV and gzip-compressed sources work the same way:

```python
result = compare_sources(
    "old.tsv.gz",
    "new.tsv.gz",
    first_kind="tsv",
    second_kind="tsv",
    key="id",
)
```

CSV and TSV dialect options can be passed through connector options:

```python
result = compare_sources(
    "old.csv",
    "new.csv",
    first_options={"format": "csv", "delimiter": ";"},
    second_options={"format": "csv", "delimiter": ";"},
    key="id",
)
```

Headerless files can be mapped to dictionaries with `fieldnames`:

```python
result = compare_sources(
    "old.csv",
    "new.csv",
    first_options={"format": "csv", "has_header": False, "fieldnames": ("id", "name")},
    second_options={"format": "csv", "has_header": False, "fieldnames": ("id", "name")},
    key="id",
)
```

Parquet support is intentionally optional:

```bash
pip install "uniqdiff[parquet]"
```

```python
result = compare_sources(
    "old.parquet",
    "new.parquet",
    first_kind="parquet",
    second_kind="parquet",
    first_options={"columns": ("id", "name"), "batch_size": 100_000},
    second_options={"columns": ("id", "name"), "batch_size": 100_000},
    key="id",
)
```

For automatic source selection:

```python
result = compare_sources([1, 2, 3], [2, 4])
```

## Custom Connectors

```python
from collections.abc import Iterator
from typing import Any

from uniqdiff import register_connector


class StaticConnector:
    name = "static"

    def __init__(self, source: list[Any]) -> None:
        self.source = source

    def open(self) -> Iterator[Any]:
        yield from self.source

    def describe(self) -> dict[str, Any]:
        return {"connector": self.name}


register_connector("static", StaticConnector)
```

Connectors are intentionally lightweight. Future connectors can wrap S3, HTTP APIs,
databases, queues, or enterprise storage systems.
