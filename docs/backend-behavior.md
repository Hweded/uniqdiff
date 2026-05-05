# Backend Behavior

This page documents the expected behavior of `uniqdiff` backends for the 1.0 API.

## Memory Backend

Selected by:

- `mode="memory"`;
- `mode="auto"` when the input estimate fits the configured memory limit.

Behavior:

- materializes comparison indexes in RAM;
- returns in-memory `CompareResult` lists;
- preserves first-seen value for each comparison token;
- supports `include_common` and `include_duplicates`.

Best for:

- small and medium inputs;
- scripts;
- tests;
- interactive workflows.

Limits:

- input and output must fit available memory;
- Python object overhead can be significant for large rows.

## SQLite Backend

Selected by:

- `mode="disk", disk_strategy="sqlite"`;
- `mode="auto"` when disk mode is selected and no other disk strategy is provided.

Behavior:

- stores comparison tokens and row payloads in a temporary SQLite database;
- consumes iterables incrementally;
- supports file result mode;
- writes temporary data under `temp_dir` when provided.

Best for:

- reliable exact comparison with lower peak memory;
- generators and unsized inputs;
- large result sets with `result_mode="file"`.

Limits:

- slower than memory mode;
- performance depends on disk I/O;
- temporary storage must have enough space.

## Hash Partition Backend

Status: stable 1.0 backend, documented as an advanced mode.

Selected by:

- `mode="disk", disk_strategy="hash_partition"`.

Behavior:

- writes rows into partition files by comparison-token hash;
- compares one partition at a time;
- equal tokens are always routed to the same partition;
- materialized result sections are restored by original input ordinal for that side.

Best for:

- very large inputs;
- cases where partition-by-partition comparison reduces peak memory.

Limits:

- requires enough disk space for partition files;
- skewed keys can create large partitions;
- too many partitions can increase file overhead.

## External Sort Backend

Status: stable 1.0 backend, documented as an advanced mode.

Selected by:

- `mode="disk", disk_strategy="external_sort"`.

Behavior:

- reads input in chunks;
- writes sorted chunk files;
- merges sorted token streams;
- supports exact comparison without loading all tokens into memory.

Best for:

- large sequential workloads;
- inputs where sorting and merge passes are acceptable;
- disk-backed exact comparison with predictable passes.

Limits:

- materialized result sections are restored by original input ordinal for that side;
- disk I/O can dominate runtime;
- chunk size affects both memory and performance.

## Auto Mode

Status: stable 1.0 mode, documented as an advanced selection mode because its
decision metadata is part of the contract and the heuristic may be refined in
backward-compatible ways.

Selected by:

- `mode="auto"`.

Behavior:

- chooses memory or disk using documented metadata;
- selects disk when `result_mode="file"`;
- selects disk when `temp_dir` is provided;
- uses `memory_limit` and a safety factor for sized inputs;
- selects disk for unsized input when `memory_limit` is provided.

The decision is available in:

```python
result.metadata["auto_decision"]
```

## File Result Mode

Selected by:

- `result_mode="file"`;
- requires `mode="disk"` or `mode="auto"`;
- requires `output`.

Behavior:

- writes result rows directly to `.jsonl` or `.csv`;
- does not materialize result lists in memory;
- returns stats and metadata;
- supports lazy reading with `iter_result_rows()` and `iter_result_values()`.

## Backend Compatibility Contract

All exact backends should agree on comparison semantics:

- same comparison token rules;
- same stats counts;
- same duplicate semantics;
- same set of unique values.

Current exact backends emit materialized result sections in original input order for
the corresponding side. Users should still avoid treating ordering as the primary
cross-backend semantic contract; compare by section values and stats when possible.
