# Streaming Diff

`iter_sorted_diff()` provides exact streaming comparison for inputs that are
already sorted by the comparison token.

It is useful when:

- both inputs are sorted by the same key;
- the caller wants rows as soon as they are known;
- temporary files are undesirable;
- the full diff output may be large.

## Example

```python
from uniqdiff import iter_sorted_diff

left = [{"id": 1}, {"id": 2}, {"id": 4}]
right = [{"id": 2}, {"id": 3}, {"id": 4}]

for row in iter_sorted_diff(left, right, key="id", include_common=True):
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
rows = iter_sorted_diff(
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

## Requirements

Both inputs must be sorted by the same token produced from `key` and
`normalizer`.

By default, `validate_sorted=True` raises `InvalidInputError` when descending
tokens are detected. Set `validate_sorted=False` only when the caller already
guarantees sorted input and wants to skip that check.

Comparison tokens must be orderable with `<`. For complex objects, pass a
sortable `key`.

## Limitations

`iter_sorted_diff()` is exact, but it is not a general replacement for
`compare()`.

It does not:

- sort inputs;
- build indexes;
- write temporary files;
- return `CompareResult` or `CompareStats`;
- support arbitrary unsorted streams.

Use regular `compare()` with memory or disk backends when inputs are not already
sorted.
