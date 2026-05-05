# UniqTools Starter

This example shows the recommended first integration layer for UniqTools-style
packages.

The example intentionally uses only the public `uniqdiff` API:

- `compare_files`;
- `CompareResult`;
- `CompareResult.iter_section`;
- result metadata and stats.

It does not import `uniqdiff.core`, `uniqdiff.storage`, or any backend internals.

## Run

From the repository root:

```bash
python examples/uniqtools_starter/engine_adapter.py
```

The script creates two temporary CSV files under `.tmp/uniqtools_starter`,
compares them by `id`, writes the large-result-friendly JSONL output to a
temporary file, prints a compact summary that a higher-level tool could use, and
then removes the temporary workspace.

## Why This Shape

Future packages such as `uniqrowdiff`, `uniqcheck`, and `uniqreport` should treat
`uniqdiff` as a stable engine dependency:

```toml
dependencies = ["uniqdiff>=1.0,<2.0"]
```

Tool-specific behavior should live outside `uniqdiff`. For example:

- row-level changed fields belong in `uniqrowdiff`;
- HTML/PDF/Excel output belongs in `uniqreport`;
- workflow orchestration belongs in `uniqtools-cli`;
- data quality rules belong in `uniqcheck`.
