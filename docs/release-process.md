# Release Process

This page documents the manual release flow for `uniqdiff` 1.0.x.

## Preconditions

- `pyproject.toml` has the target version.
- `pyproject.toml` uses the Apache-2.0 license metadata.
- `CHANGELOG.md` has a section for the target version.
- `docs/release-notes-1.0.md` is current for the release.
- Public/internal API boundary docs are current.
- Result schema docs are current.
- Backend behavior docs are current.
- CI passes on all supported Python versions.

## Local Validation

Run:

```bash
python -m ruff check .
python -m mypy src
python -m pytest --cov=uniqdiff --cov-report=term-missing
python -m build --sdist --wheel
python -m twine check dist/*
```

Expected release quality:

- tests pass;
- coverage is at least 85%;
- sdist and wheel build successfully;
- package metadata passes `twine check`.
- commercial/support/service docs are present if the release advertises commercial
  support.

## Artifact Names

For `1.0.0`, the expected artifacts are:

- `dist/uniqdiff-1.0.0.tar.gz`;
- `dist/uniqdiff-1.0.0-py3-none-any.whl`.

## Publishing

Publish to TestPyPI first:

```bash
python -m twine upload --repository testpypi dist/*
```

Install from TestPyPI in a clean environment and smoke-test:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple uniqdiff
python -m uniqdiff --help
```

Publish to PyPI only after TestPyPI smoke tests pass:

```bash
python -m twine upload dist/*
```

## Git Tag

Create an annotated release tag:

```bash
git tag -a v1.0.0 -m "Release uniqdiff 1.0.0"
git push origin v1.0.0
```

## Post-Release Checks

- Confirm package page renders correctly on PyPI.
- Confirm `pip install uniqdiff` works in a clean environment.
- Confirm `python -m uniqdiff --help` works.
- Confirm README links resolve.
- Create the GitHub release from the `v1.0.0` tag using the release notes.
