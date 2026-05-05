# Auto Mode

`mode="auto"` chooses between memory and disk backends using a simple documented
heuristic.

Disk is selected when:

- `result_mode="file"`;
- `temp_dir` is provided;
- `memory_limit` is provided and estimated input size exceeds it;
- input size is unknown and `memory_limit` is provided.

Otherwise memory backend is used.

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
- `reason`.

The estimate is intentionally conservative. It is designed to avoid surprising memory
growth, not to predict exact Python object size.
