# CI/CD

The GitHub Actions workflow is defined in:

```text
.github/workflows/ci.yml
```

It runs:

- tests on Python 3.9 through 3.14;
- `compileall`;
- `ruff`;
- `mypy`;
- package build;
- benchmark smoke.

Local equivalent:

```bash
python -m pytest
python -m ruff check .
python -m mypy src/uniqdiff
python -m build --sdist --wheel
python benchmarks/run.py --size 1000 --scenario memory --scenario sqlite --json
```
