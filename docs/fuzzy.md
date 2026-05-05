# Fuzzy Comparison

Fuzzy comparison is available through a separate helper:

```python
from uniqdiff import compare_fuzzy_strings

result = compare_fuzzy_strings(["Alice Smith"], ["alice smyth"], threshold=75)
```

This API is intentionally separate from exact `compare` and is not part of the exact
comparison engine semantics.

## Behavior

- Greedy matching.
- Approximate scores from 0 to 100.
- `rapidfuzz.WRatio` is used when `rapidfuzz` is installed.
- `difflib.SequenceMatcher` is used as a stdlib fallback.

## Installation

```bash
pip install "uniqdiff[fuzzy]"
```

## Limitations

Fuzzy comparison is approximate, greedy, and `O(n*m)`. It is best for small or medium
string lists and is not recommended for very large datasets without indexing or
blocking.
