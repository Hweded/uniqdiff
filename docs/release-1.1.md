# Release 1.1 Checklist

This page records what must be true for `uniqdiff` 1.1.0.

## Release Goal

1.1.0 promotes the post-1.0 engine work into a stable additive release:

- field-level diff by key;
- schema-aware diff;
- sorted streaming diff;
- versioned JSONL event streams;
- bounded JSONL output;
- explicit `uniqdiff.engine` facade;
- profiling and benchmark improvements.

## Included Engine Surface

- [x] Core 1.0 comparison API remains stable.
- [x] `uniqdiff.engine` facade exists and is covered by tests.
- [x] Field-diff APIs are documented and tested.
- [x] Sorted field-diff APIs are documented and tested.
- [x] Schema-diff APIs are documented and tested.
- [x] JSONL event stream APIs are documented and tested.
- [x] JSONL event stream keeps schema version `1.0`.
- [x] CLI flags for field diff, schema diff, JSONL output, and output limits are tested.
- [x] Benchmarks are reproducible and documented.

## Required Validation

Run before publishing:

```bash
python -m ruff check src tests
python -m mypy src
python -m pytest tests -q
python -m build --sdist --wheel
python -m twine check dist/*
```

Optional benchmark smoke:

```bash
python benchmarks/run.py --size 1000 --scenario memory --scenario sqlite --json
python benchmarks/comparison/run.py --adapter uniqdiff --profile orders --rows 1000
```

## Release Artifacts

Expected package artifacts:

- `dist/uniqdiff-1.1.0.tar.gz`;
- `dist/uniqdiff-1.1.0-py3-none-any.whl`.

## Publish Checklist

- [ ] `pyproject.toml` version is `1.1.0`.
- [ ] `src/uniqdiff/_version.py` version is `1.1.0`.
- [ ] `CHANGELOG.md` has a `1.1.0` section.
- [ ] `docs/release-notes-1.1.md` is current.
- [ ] README benchmark summary is current.
- [ ] CI passes.
- [ ] Build artifacts pass `twine check`.
- [ ] TestPyPI smoke passes.
- [ ] Git tag `v1.1.0` is created.
- [ ] GitHub release uses the 1.1 release notes.

## Known Non-Goals

1.1.0 does not add product-layer features such as reports, workflow runners,
dashboards, SaaS logic, or enterprise connector management. Those belong in
higher-level UniqTools packages.
