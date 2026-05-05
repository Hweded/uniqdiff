# Auto Mode

`mode="auto"` chooses between memory and disk backends using a documented
heuristic. The heuristic is conservative: it prefers predictable memory use over
perfect object-size prediction.

Disk is selected when:

- `result_mode="file"`;
- `temp_dir` is provided;
- `memory_limit` is provided and estimated input size exceeds it;
- input size is unknown and `memory_limit` is provided.

Otherwise memory backend is used.

## Auto Disk Strategy

By default, disk mode still uses SQLite unless the caller selects another
strategy. For automatic disk-backend selection, pass:

```python
result = compare(
    first,
    second,
    mode="auto",
    disk_strategy="auto",
    memory_limit="512MB",
    preserve_order=False,
)
```

When `disk_strategy="auto"` is used, the planner may choose:

- `sqlite` for small disk-backed jobs, unsized inputs, file result mode, or when
  original ordering should be preserved;
- `hash_partition` for large unordered jobs where partition-by-partition
  processing is likely to reduce peak memory;
- `external_sort` when a disk limit is configured or the workload looks better
  suited for chunk-sort-merge processing.

This is a planner heuristic, not a semantic difference. Exact comparison results
must remain equivalent across exact backends.

For sized inputs, the estimate uses:

- `len(first) + len(second)`;
- an internal bytes-per-item estimate;
- a memory safety factor, so auto mode switches to disk before the configured limit
  is fully consumed.

The decision is stored in:

```python
result.metadata["auto_decision"]
```

Example:

```python
result = compare(a, b, mode="auto", memory_limit="512MB")
print(result.metadata["backend"])
print(result.metadata["auto_decision"])
```

Useful metadata fields:

- `estimated_items`;
- `estimated_bytes`;
- `bytes_per_item_estimate`;
- `memory_safety_factor`;
- `memory_limit_bytes`;
- `effective_memory_limit_bytes`;
- `selected_backend`;
- `requested_disk_strategy`;
- `selected_disk_strategy`;
- `include_common`;
- `include_duplicates`;
- `preserve_order`;
- `chunk_size`;
- `reason`.

The estimate is intentionally conservative. It is designed to avoid surprising memory
growth, not to predict exact Python object size. The heuristic may be refined in
minor releases while preserving exact comparison semantics.
