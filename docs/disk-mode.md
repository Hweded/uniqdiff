# Disk Mode

`mode="disk"` is for inputs that should be consumed incrementally and indexed through
temporary disk structures.

Available strategies:

- `sqlite`;
- `hash_partition`;
- `external_sort`.

Example:

```python
from uniqdiff import compare

result = compare(
    rows_a,
    rows_b,
    key="id",
    mode="disk",
    disk_strategy="sqlite",
    chunk_size=100_000,
    temp_dir="./tmp",
    disk_limit="10GB",
)
```

Disk mode is exact, but slower than memory mode because it performs filesystem and
serialization work.

Use disk mode when:

- inputs are large;
- inputs are generators;
- memory pressure matters;
- you need file result mode.
