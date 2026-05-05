# Quick Start

Install the stable package first:

```bash
pip install uniqdiff
```

Install optional Parquet support when needed:

```bash
pip install "uniqdiff[parquet]"
```

For local development:

```bash
pip install -e ".[dev]"
```

Compare two simple iterables:

```python
from uniqdiff import compare

result = compare([1, 2, 3], [3, 4, 5], include_common=True)

assert result.only_in_first == [1, 2]
assert result.only_in_second == [4, 5]
assert result.common == [3]
```

Compare dictionaries by key:

```python
from uniqdiff import compare_by_key

old = [{"id": 1}, {"id": 2}]
new = [{"id": 2}, {"id": 3}]

result = compare_by_key(old, new, key="id")
```

Compare files:

```python
from uniqdiff import compare_files

result = compare_files("old.csv", "new.csv", format="csv", key="id")
result = compare_files("old.tsv.gz", "new.tsv.gz", format="tsv", key="id")
result = compare_files("old.parquet", "new.parquet", format="parquet", key="id")
```

Use CLI:

```bash
uniqdiff compare old.csv new.csv --format csv --key id
uniqdiff compare old.tsv.gz new.tsv.gz --format tsv --key id
uniqdiff compare old.csv new.csv --format csv --key id --summary
uniqdiff diff old.csv new.csv --format csv --key id --summary --fail-on-diff
```
