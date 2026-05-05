# uniqrowdiff Prototype

This is a small product-layer prototype for the future `uniqrowdiff` package.

It demonstrates how a UniqTools package can build row-level changed-field
analysis on top of the stable `uniqdiff` engine without importing engine
internals.

## What It Does

The prototype compares two CSV files by a key column and reports:

- rows present only in the first file;
- rows present only in the second file;
- common keys;
- duplicate-key counts from the engine;
- changed fields for keys that exist exactly once in both files.

The field-level change output is intentionally outside `uniqdiff`. The engine
continues to own exact presence comparison, while this prototype owns
product-layer row analysis.

## Run

From the repository root:

```bash
python examples/uniqrowdiff_prototype/rowdiff.py
```

The script writes demo CSV files under `.tmp/uniqrowdiff_prototype`, generates a
JSONL row-diff artifact, prints a summary, and then removes the temporary
workspace.

## Future Package Shape

A future standalone package could expose:

```bash
uniqrowdiff old.csv new.csv --key id --output changes.jsonl
uniqrowdiff old.csv new.csv --key id --ignore updated_at --format csv
```

And depend on:

```toml
dependencies = ["uniqdiff>=1.0,<2.0"]
```

The package should continue to use only public imports from `uniqdiff`.
