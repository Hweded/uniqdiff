# Bloom Filters

Bloom filter helpers provide approximate membership checks.

```python
from uniqdiff import BloomFilter

bloom = BloomFilter(expected_items=1_000_000, false_positive_rate=0.01)
bloom.add("user-1")

if "user-1" in bloom:
    ...
```

You can also compute probabilistic difference candidates:

```python
from uniqdiff import probabilistic_diff_candidates

result = probabilistic_diff_candidates(
    first,
    second,
    expected_first=1_000_000,
    expected_second=1_000_000,
)
```

## Important Limitation

Bloom filters can produce false positives. In candidate-diff workflows, a false
positive can hide a true difference because an unseen value may look present.
Use this mode for candidate filtering, not for final exact reconciliation.

Bloom helpers are public probabilistic helpers, not part of the exact comparison
engine semantics.
