# Hash Partitioning

`disk_strategy="hash_partition"` writes each input into temporary partition files by
hashing the comparison token.

Equal tokens always go to the same partition, so each partition pair can be compared
independently.

```python
result = compare(
    rows_a,
    rows_b,
    key="id",
    mode="disk",
    disk_strategy="hash_partition",
    partition_count=128,
)
```

## When To Use

- Very large inputs.
- When partition-by-partition comparison is easier to reason about than SQLite.
- When you want a backend that can later be parallelized.

## Trade-Offs

- More files are created.
- Bad hash distribution can create uneven partitions.
- Current implementation still materializes one partition in memory at a time.

## Choosing `partition_count`

Start with 64 or 128. Increase it when partitions are too large for available memory.
Decrease it when file count overhead dominates.
