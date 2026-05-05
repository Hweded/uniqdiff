# Property-Based Tests

The test suite uses Hypothesis to compare backend semantics across generated inputs.

Covered invariants:

- memory backend matches SQLite for exact sections and counts;
- memory backend matches hash partitioning;
- memory backend matches external sort;
- duplicate outputs match as multisets;
- normalized comparisons behave consistently across backends.

Run:

```bash
python -m pytest tests/test_properties.py
```

These tests are especially important because the project has multiple storage
strategies that should preserve the same exact comparison semantics.
