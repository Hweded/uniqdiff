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
`chunk_size=4000`, and `partition_count=16`, after the first profiling-driven
storage/output optimization pass.

| Scenario | Elapsed, s | Peak MB | Primary bottleneck |
|---|---:|---:|---|
| memory | 0.012 | 1.532 | `memory._index_items`, `tokens.canonicalize_token` |
| memory_no_order | 0.011 | 2.877 | `memory._index_items`, `tokens.canonicalize_token` |
| sqlite | 0.348 | 0.893 | `storage.codec.to_blob`, `sqlite._insert_items`, SQLite `execute` |
| hash_partition | 0.732 | 3.133 | partition write/read, `storage.codec.read_record`, `storage.codec.to_blob` |
| external_sort | 0.764 | 2.880 | `_merge_grouped`, `_group_sorted_records`, `heapq.merge` |
| file_result | 0.514 | 0.965 | SQLite insert/fetch, `StreamingResultWriter.write`, JSON value encoding |
| sorted_stream | 0.134 | 3.301 | `streaming._group_sorted`, token comparisons |
| sorted_stream_file | 0.179 | 0.185 | streaming merge and JSON value encoding |

Compared with the previous local snapshot on the same workload, the first pass
reduced elapsed time by roughly:

- `sqlite`: from `0.414s` to `0.348s`;
- `hash_partition`: from `0.888s` to `0.732s`;
- `external_sort`: from `0.955s` to `0.764s`;
- `file_result`: from `0.862s` to `0.514s`;
- `sorted_stream_file`: from `0.419s` to `0.179s`.

The main changes were:

- compact temporary scalar encoding for disk backends;
- length-prefixed binary temporary records for hash partition and external sort;
- leaner JSONL row writing that avoids allocating a full row dict per output row;
- fast JSON value encoding for common scalar output values.

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

The main cost is payload encoding and database insertion:

- `storage.codec.to_blob`;
- `sqlite._insert_items`;
- SQLite `execute`;
- result section fetches.

Likely improvements:

- batch insert tuning;
- more scalar-specialized payload encoding;
- optional compact row encoding for simple tokens;
- avoid fetching materialized sections when file output is requested.

### Hash Partition

The main cost is partition writing, reading, and grouping:

- `_write_partitions`;
- `_read_partition`;
- `storage.codec.write_record`;
- `storage.codec.read_record`;
- `storage.codec.to_blob`.

Likely improvements:

- buffered partition writers;
- fewer file open/close cycles;
- parallel partition processing after correctness and ordering semantics are
  documented.

### External Sort

The main cost is merge/group iteration after temporary record encoding was
reduced:

- `_write_sorted_chunks`;
- `_merge_grouped`;
- `_group_sorted_records`;
- `_merge_chunks`.

Likely improvements:

- tune chunk size;
- specialize merge for scalar tokens;
- avoid materializing result sections when direct file output is requested.

### File Result Mode

For scalar-heavy JSONL output, row writing is no longer dominated by a full
`json.dumps` call per row. The remaining cost is split across:

- `StreamingResultWriter.write`;
- scalar JSON value encoding;
- file writes;
- upstream SQLite fetch/insert work in `file_result` mode.

Likely improvements:

- batch buffering for JSONL lines;
- optional faster JSON writer for structured values;
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

1. Tune SQLite batch insertion and fetch paths.
2. Explore buffered hash partition writers and larger partition buffers.
3. Specialize external sort merge paths for scalar tokens.
4. Add optional faster JSON output under a separate optional extra, not core.
5. Add larger profiling runs for dict rows and key-based comparison.
