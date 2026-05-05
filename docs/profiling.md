# Profiling

`benchmarks/profile_modes.py` profiles `uniqdiff` execution modes with
standard-library `cProfile` and `tracemalloc`.

The goal is to find bottlenecks in the current implementation. Results are
workload-dependent and should not be treated as universal performance claims.

## Run

```bash
python benchmarks/profile_modes.py --size 20000
```

Focused run:

```bash
python benchmarks/profile_modes.py \
  --size 10000 \
  --scenario memory \
  --scenario sqlite \
  --scenario sorted_stream_file
```

Outputs:

- `benchmarks/results/profile-results.jsonl`;
- `benchmarks/results/profile-report.md`.

`benchmarks/results/` is ignored by git because profiling output is
machine-specific.

## Scenarios

- `memory`;
- `memory_no_order`;
- `sqlite`;
- `hash_partition`;
- `external_sort`;
- `file_result`;
- `sorted_stream`;
- `sorted_stream_file`.

## Local Snapshot

Snapshot from a local run on `12_000` rows per input, `50%` overlap,
`chunk_size=4000`, and `partition_count=16`.

| Scenario | Elapsed, s | Peak MB | Primary bottleneck |
|---|---:|---:|---|
| memory | 0.013 | 1.532 | `memory._index_items`, `tokens.canonicalize_token` |
| memory_no_order | 0.014 | 2.877 | `memory._index_items`, `tokens.canonicalize_token` |
| sqlite | 0.414 | 0.961 | `_pickle.dumps`, `sqlite._insert_items`, SQLite `execute` |
| hash_partition | 0.888 | 3.190 | partition write/read, `_pickle.dumps`, `_pickle.load` |
| external_sort | 0.955 | 3.246 | `_merge_grouped`, `_write_sorted_chunks`, chunk merge/grouping |
| file_result | 0.862 | 1.022 | `StreamingResultWriter.write`, `json.dumps`, SQLite insert |
| sorted_stream | 0.112 | 3.301 | `streaming._group_sorted`, token comparisons |
| sorted_stream_file | 0.419 | 0.174 | `json.dumps`, `StreamingResultWriter.write`, streaming merge |

## Findings

### Memory Mode

The hot path is token indexing:

- `memory._index_items`;
- `tokens.canonicalize_token`.

Likely improvements:

- keep scalar-token fast paths tight;
- avoid extra canonicalization for already scalar keys;
- benchmark key-based dict rows separately because key extraction changes the hot
  path.

### SQLite Disk Mode

The main cost is payload serialization and database insertion:

- `_pickle.dumps`;
- `sqlite._insert_items`;
- SQLite `execute`;
- result section fetches.

Likely improvements:

- batch insert tuning;
- faster payload encoding for scalar values;
- optional compact row encoding for simple tokens;
- avoid fetching materialized sections when file output is requested.

### Hash Partition

The main cost is partition serialization and deserialization:

- `_write_partitions`;
- `_read_partition`;
- `_pickle.dumps`;
- `_pickle.load`.

Likely improvements:

- compact binary/text encoding for scalar rows;
- buffered partition writers;
- fewer file open/close cycles;
- parallel partition processing after correctness and ordering semantics are
  documented.

### External Sort

The main cost is chunk writing and merge/group iteration:

- `_write_sorted_chunks`;
- `_merge_grouped`;
- `_group_sorted_records`;
- `_merge_chunks`.

Likely improvements:

- reduce pickle overhead for scalar rows;
- tune chunk size;
- specialize merge for scalar tokens;
- avoid materializing result sections when direct file output is requested.

### File Result Mode

For JSONL output, `json.dumps` dominates row writing:

- `StreamingResultWriter.write`;
- `json.dumps`;
- JSON encoder internals.

Likely improvements:

- faster JSON writer path for scalar values;
- optional compact separators;
- batch buffering for JSONL lines;
- consider optional faster JSON extra in a separate optional dependency, not core.

### Sorted Streaming

For in-memory list consumption, the merge itself is fast but every emitted row is
still materialized by the caller. For direct file output, memory stays low and
JSON serialization becomes the bottleneck.

Likely improvements:

- reduce per-row dict allocation in streaming rows where possible;
- keep `validate_sorted=False` available for trusted sorted inputs;
- add direct adapters in tools that consume row tuples internally before writing
  final artifacts.

## Current Optimization Priorities

1. Add compact serialization paths for scalar values in disk backends.
2. Optimize JSONL output writes for file result and sorted streaming output.
3. Tune SQLite batch insertion and fetch paths.
4. Explore buffered hash partition writers.
5. Add larger profiling runs for dict rows and key-based comparison.
