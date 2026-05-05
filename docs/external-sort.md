# External Sort

`disk_strategy="external_sort"` sorts chunks on disk and then performs a merge pass over
both sorted token streams.

```python
result = compare(
    rows_a,
    rows_b,
    key="id",
    mode="disk",
    disk_strategy="external_sort",
    chunk_size=250_000,
)
```

## When To Use

- Inputs can be sorted by a stable comparison token.
- You want predictable chunk memory.
- You expect many duplicate or repeated keys.

## Trade-Offs

- Sorting costs more CPU than simple hashing.
- Temporary chunk files are written to disk.
- Materialized result sections are restored by original input ordinal for that side
  after merge.
- Ordering is not the primary cross-backend semantic contract; section values and
  stats are.
