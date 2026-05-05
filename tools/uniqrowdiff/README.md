# uniqrowdiff

`uniqrowdiff` is the first UniqTools package prototype built on top of the
stable `uniqdiff` engine.

It answers a product-layer question that does not belong in `uniqdiff` itself:

> For rows with the same key, which fields changed?

`uniqdiff` remains responsible for exact presence comparison and duplicate
counts. `uniqrowdiff` consumes those facts and adds row-level changed-field
analysis.

## Current Scope

This scaffold currently supports:

- CSV input;
- key-based matching;
- ignored fields;
- JSONL output for changed rows;
- summary JSON for CLI/CI;
- optional non-zero exit code when changes, added rows, or removed rows are
  found.

It intentionally does not include reports, dashboards, workflow orchestration,
or enterprise connector management.

## Local Development

From the repository root, use both source roots on `PYTHONPATH`.

PowerShell:

```powershell
$env:PYTHONPATH = "src;tools/uniqrowdiff/src"
python -m uniqrowdiff --help
python -m uniqrowdiff old.csv new.csv --key id --output changes.jsonl
```

Bash:

```bash
PYTHONPATH=src:tools/uniqrowdiff/src python -m uniqrowdiff --help
PYTHONPATH=src:tools/uniqrowdiff/src python -m uniqrowdiff old.csv new.csv --key id --output changes.jsonl
```

## CLI Examples

```bash
uniqrowdiff old.csv new.csv --key id --ignore updated_at --output changes.jsonl
uniqrowdiff old.csv new.csv --key id --fail-on-changes
uniqrowdiff old.csv new.csv --key id --fail-on-added --fail-on-removed
```

Exit codes:

- `0`: command completed and no selected failure condition was triggered;
- `1`: selected failure condition was triggered;
- `2`: invalid input or usage error.

## Architecture Rule

This package should depend only on public `uniqdiff` imports:

```python
from uniqdiff import CompareResult, compare_files
```

It should not import `uniqdiff.core`, `uniqdiff.storage`, `uniqdiff.planner`, or
private helper modules.
