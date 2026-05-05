# Contributing

Thank you for considering a contribution to `uniqdiff`.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src/uniqdiff
```

## Commit Style

Use clear, focused commits. Conventional Commits are recommended:

- `feat: add csv comparison`
- `fix: handle missing dictionary keys`
- `docs: expand quick start`

## Pull Requests

Pull requests should include tests for behavioral changes and documentation for public API changes.
