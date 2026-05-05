# Tools

This directory contains early UniqTools package scaffolds built on top of the
stable `uniqdiff` engine.

Tools in this directory are not part of the `uniqdiff` public API. They exist to
validate ecosystem packages before they are moved to standalone repositories or
published independently.

## Current Tools

- [`uniqrowdiff`](uniqrowdiff/README.md): row-level changed-field analysis for
  CSV rows matched by key.

## Boundary Rule

Tools should depend only on documented public `uniqdiff` APIs:

- root package exports;
- `CompareResult` and `CompareStats`;
- file result schema and lazy readers;
- connector protocol when needed.

Tools should not import `uniqdiff` internal modules such as `uniqdiff.core`,
`uniqdiff.planner`, or `uniqdiff.storage`.
