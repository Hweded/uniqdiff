# File Result Mode

`result_mode="file"` writes result rows directly to `.jsonl` or `.csv` output. The
returned `CompareResult` contains stats and metadata but not materialized result lists.

```python
result = compare(
    rows_a,
    rows_b,
    key="id",
    mode="disk",
    result_mode="file",
    output="diff.jsonl",
)
```

Each output row has:

- `section`;
- `value`.

The stable row schema is documented in [Result Schema](result-schema.md).

Sections:

- `only_in_first`;
- `only_in_second`;
- `common`;
- `duplicates_first`;
- `duplicates_second`.

Use file result mode when the output itself can be large.

## Lazy Reading

Result files can be read lazily without loading the whole diff into memory:

```python
from uniqdiff import iter_result_values

for row in iter_result_values("diff.jsonl", sections=("only_in_first",)):
    process(row)
```

You can also read complete result rows:

```python
from uniqdiff import iter_result_rows

for row in iter_result_rows("diff.csv"):
    print(row["section"], row["value"])
```

When a `CompareResult` was produced with `result_mode="file"`, these helpers are
available through the result object:

```python
result = compare(a, b, mode="disk", result_mode="file", output="diff.jsonl")

for value in result.iter_unique():
    process(value)

for value in result.iter_section("only_in_second"):
    process(value)
```
