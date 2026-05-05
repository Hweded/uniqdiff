# Recipes

Short practical examples for common `uniqdiff` workflows.

## Compare Two CSV Files

```python
from uniqdiff import compare_files

result = compare_files("old.csv", "new.csv", format="csv", key="id")

print(result.only_in_first)
print(result.only_in_second)
```

CLI:

```bash
uniqdiff compare old.csv new.csv --format csv --key id
```

## Find New Rows

Rows that exist only in the second file are usually "new" rows.

```python
from uniqdiff import compare_files

result = compare_files("old.csv", "new.csv", format="csv", key="id")

new_rows = result.only_in_second
```

CLI summary:

```bash
uniqdiff compare old.csv new.csv --format csv --key id --summary
```

## Find Removed Rows

Rows that exist only in the first file are usually "removed" rows.

```python
from uniqdiff import compare_files

result = compare_files("old.csv", "new.csv", format="csv", key="id")

removed_rows = result.only_in_first
```

## Compare By Key

Use `key` when rows are dictionaries, objects, or dataclasses.

```python
from uniqdiff import compare_by_key

old = [{"id": 1, "email": "a@example.com"}]
new = [{"id": 2, "email": "b@example.com"}]

result = compare_by_key(old, new, key="id")
```

Composite keys are supported:

```python
result = compare_by_key(old, new, key=("country", "id"))
```

## Write Result To JSON

For small and medium results:

```python
from uniqdiff import compare_files

result = compare_files(
    "old.csv",
    "new.csv",
    format="csv",
    key="id",
    output="result.json",
)
```

CLI:

```bash
uniqdiff diff old.csv new.csv --format csv --key id --output result.json
```

## Write Large Result To JSONL

Use `result_mode="file"` for large outputs.

```python
from uniqdiff import compare_files

result = compare_files(
    "old.csv",
    "new.csv",
    format="csv",
    key="id",
    mode="disk",
    result_mode="file",
    output="result.jsonl",
)

print(result.stats.only_in_first_count)
print(result.stats.only_in_second_count)
```

CLI:

```bash
uniqdiff compare old.csv new.csv \
  --format csv \
  --key id \
  --mode disk \
  --result-mode file \
  --output result.jsonl
```

## Write Large Result To CSV

```python
from uniqdiff import compare_files

result = compare_files(
    "old.csv",
    "new.csv",
    format="csv",
    key="id",
    mode="disk",
    result_mode="file",
    output="result.csv",
)
```

Each output row contains:

- `section`;
- `value`.

## Read Large Results Lazily

```python
from uniqdiff import iter_result_values

for row in iter_result_values("result.jsonl", sections=("only_in_second",)):
    process(row)
```

File-backed `CompareResult` can also stream values:

```python
for row in result.iter_unique():
    process(row)
```

## Compare TSV Or Gzip Files

```python
from uniqdiff import compare_files

result = compare_files("old.tsv.gz", "new.tsv.gz", format="tsv", key="id")
```

CLI:

```bash
uniqdiff compare old.tsv.gz new.tsv.gz --format tsv --key id
```

## Compare Headerless CSV

```python
from uniqdiff import compare_files

result = compare_files(
    "old.csv",
    "new.csv",
    format="csv",
    has_header=False,
    fieldnames=("id", "name"),
    key="id",
)
```

CLI:

```bash
uniqdiff compare old.csv new.csv \
  --format csv \
  --no-header \
  --fieldnames id,name \
  --key id
```

## CI Check For Differences

Return exit code `1` when differences exist:

```bash
uniqdiff diff old.csv new.csv --format csv --key id --summary --fail-on-diff
```
