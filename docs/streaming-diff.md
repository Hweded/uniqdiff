# Streaming Diff

`compare_sorted_iter()` and `iter_sorted_diff()` provide exact streaming
comparison for inputs that are already sorted by the comparison token.

It is useful when:

- both inputs are sorted by the same key;
- the caller wants rows as soon as they are known;
- temporary files are undesirable;
- the full diff output may be large.

## Example

```python
from uniqdiff import compare_sorted_iter

left = [{"id": 1}, {"id": 2}, {"id": 4}]
right = [{"id": 2}, {"id": 3}, {"id": 4}]

for row in compare_sorted_iter(left, right, key="id", include_common=True):
    print(row)
```

Output rows use the same section/value shape as file result mode:

```python
{"section": "only_in_first", "value": {"id": 1}}
{"section": "common", "value": {"id": 2}}
{"section": "only_in_second", "value": {"id": 3}}
{"section": "common", "value": {"id": 4}}
```

## Duplicates

Pass `include_duplicates=True` to emit duplicates inside each input. The first
value in an equal-token group is treated as the representative row; later values
in the same group are emitted as duplicates.

```python
rows = compare_sorted_iter(
    left,
    right,
    key="id",
    include_common=True,
    include_duplicates=True,
)
```

Possible sections:

- `only_in_first`;
- `only_in_second`;
- `common`;
- `duplicates_first`;
- `duplicates_second`.

## Direct File Output

Use `write_sorted_diff_file()` to stream sorted diff rows directly to JSONL or
CSV output:

```python
from uniqdiff import write_sorted_diff_file

rows_written = write_sorted_diff_file(
    left,
    right,
    "diff.jsonl",
    key="id",
    include_common=True,
)
```

The output uses the same `section` / `value` schema as file result mode and can
be read with `iter_result_rows()` or `iter_result_values()`.

`write_sorted_diff()` is the lower-level helper with the same behavior.

## Sorted Field Diff

Use `iter_field_diff_sorted()` to stream changed fields for matching-key rows
without indexing the second input:

```python
from uniqdiff import iter_field_diff_sorted

rows = iter_field_diff_sorted(
    old_rows,
    new_rows,
    key="id",
    columns=("price", "status"),
)

for row in rows:
    print(row)
```

Each yielded row has:

```python
{"key": "123", "changes": [{"field": "price", "left": 10, "right": 12}]}
```

Both inputs must be sorted by the same key. With `validate_sorted=True`, the helper
raises `InvalidInputError` if it sees keys out of order.

The same mode is available from the CLI for files:

```bash
uniqdiff diff old.csv new.csv \
  --format csv \
  --key id \
  --field-diff \
  --sorted-input \
  --columns price,status \
  --output changed-fields.jsonl \
  --summary
```

This path streams changed field rows and avoids indexing the second input. Summary
output contains changed-row and changed-field counters; full input row counts are
intentionally not materialized in this mode.

## Requirements

Both inputs must be sorted by the same token produced from `key` and
`normalizer`.

By default, `validate_sorted=True` raises `InvalidInputError` when descending
tokens are detected. Set `validate_sorted=False` only when the caller already
guarantees sorted input and wants to skip that check.

Comparison tokens must be orderable with `<`. For complex objects, pass a
sortable `key`.

## Limitations

`compare_sorted_iter()` is exact, but it is not a general replacement for
`compare()`. `iter_sorted_diff()` is the lower-level helper with the same row
semantics.

It does not:

- sort inputs;
- build indexes;
- write temporary files;
- return `CompareResult` or `CompareStats`;
- support arbitrary unsorted streams.

Use regular `compare()` with memory or disk backends when inputs are not already
sorted.
