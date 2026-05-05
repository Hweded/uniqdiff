# UniqTools Concept

UniqTools is an ecosystem of small data comparison tools built on top of the
stable `uniqdiff` engine.

The goal is to keep `uniqdiff` focused on exact comparison semantics while
higher-level packages provide workflows, reports, row-level analysis, data
quality checks, and integrations.

## Core Idea

`uniqdiff` answers engine-level questions:

- which records exist only in the first source;
- which records exist only in the second source;
- which records are common by an exact token;
- which records are duplicated by an exact token;
- how the comparison was executed and which backend was used.

UniqTools packages turn those engine facts into user-facing workflows:

- profiling inputs before comparison;
- detecting schema drift;
- comparing changed fields inside matching rows;
- producing reports;
- running CI checks;
- orchestrating repeatable local workflows.

## Product Boundary

`uniqdiff` should remain an Apache-2.0 open-source engine. It should not contain
product-layer behavior such as report templates, workflow runners, dashboards,
project management, cloud connector management, or licensing logic.

UniqTools should depend on the public `uniqdiff` API and treat the engine as a
stable library dependency.

```text
local files / streams / connectors
        |
        v
uniqdiff stable comparison engine
        |
        v
CompareResult / CompareStats / file result schema / lazy readers
        |
        v
UniqTools product packages
        |
        v
reports / checks / row diff / workflows / integrations
```

## Planned Packages

### uniqprofile

Profiles input files and streams before comparison.

Responsibilities:

- row count and approximate size;
- column names for structured files;
- null and empty value counts;
- duplicate key preview;
- basic type hints inferred from values.

It should not perform exact diff itself. When it needs comparison, it should call
`uniqdiff`.

### uniqschema

Infers and validates schemas for CSV, TSV, JSONL, and Parquet-like sources.

Responsibilities:

- schema inference;
- schema validation;
- schema drift detection;
- compatibility checks between old and new files.

It should produce schema facts, not comparison engine internals.

### uniqcheck

Runs data quality checks for scripts and CI/CD.

Responsibilities:

- required columns;
- duplicate key policies;
- row count thresholds;
- allowed drift checks;
- CLI-friendly exit codes.

It may call `uniqdiff` for duplicate detection and presence checks.

### uniqrowdiff

Compares changed fields for rows that share the same key.

Responsibilities:

- match rows by key;
- report field-level changes;
- support ignore columns and normalization rules;
- emit JSONL/CSV output suitable for reports and CI.

This package is the natural home for row-level changed-fields logic. `uniqdiff`
should continue to answer whether a key is present, common, or duplicated.

### uniqreport

Builds human-readable reports from engine and tool outputs.

Responsibilities:

- HTML reports;
- PDF or Excel reports if optional dependencies are installed;
- summary charts;
- report templates;
- links to source artifacts.

Reports should consume `uniqdiff` result files or UniqTools intermediate JSONL
artifacts. They should not change comparison semantics.

### uniqtools-cli

Provides a higher-level CLI that orchestrates several tools.

Responsibilities:

- multi-step workflows;
- repeatable local jobs;
- CI-friendly commands;
- optional config files;
- integration of `uniqdiff`, `uniqprofile`, `uniqschema`, `uniqcheck`,
  `uniqrowdiff`, and `uniqreport`.

The `uniqdiff` CLI remains the direct engine CLI. `uniqtools-cli` becomes the
workflow CLI.

## Stable Contracts Consumed From uniqdiff

UniqTools packages should use only documented `uniqdiff` contracts:

- root exports such as `compare`, `compare_files`, `compare_sources`,
  `duplicates`, and `duplicates_source`;
- `CompareResult` and `CompareStats`;
- file result schema with `section` and `value`;
- lazy readers such as `iter_result_rows` and `iter_result_values`;
- connector protocol and registry helpers;
- documented exception classes;
- documented CLI behavior for shell-level integration.

UniqTools packages should not import:

- `uniqdiff.core`;
- `uniqdiff.planner`;
- `uniqdiff.storage`;
- backend modules;
- private modules whose names start with `_`.

## First Implementation Shape

The first UniqTools implementation should be intentionally small:

1. Keep `uniqdiff` unchanged as the comparison engine.
2. Add a tiny adapter layer in a separate package or example.
3. Use `compare_files(..., result_mode="file")` for large output.
4. Read sections with `CompareResult.iter_section(...)` or
   `iter_result_values(...)`.
5. Build summaries outside the engine.
6. Add tool-specific output schemas only in the tool package.

This makes the architecture easy to test and easy to split into separate
repositories later.

## Suggested Monorepo Layout For Future Work

If UniqTools starts as one workspace, a practical layout is:

```text
uniqtools/
  packages/
    uniqprofile/
    uniqschema/
    uniqcheck/
    uniqrowdiff/
    uniqreport/
    uniqtools-cli/
  docs/
    architecture.md
    workflows.md
    commercial-support.md
  examples/
    compare-two-csv/
    ci-check/
    row-diff-report/
  pyproject.toml
  README.md
```

`uniqdiff` can remain a separate repository and dependency:

```toml
dependencies = ["uniqdiff>=1.0,<2.0"]
```

## MVP Recommendation

The most useful first product-layer MVP is `uniqrowdiff` plus a thin
`uniqtools-cli` command.

Why:

- users often need to know not only which keys were added or removed, but which
  fields changed for matching keys;
- this is clearly outside exact presence comparison;
- it creates immediate value for CSV/JSONL workflows;
- it can reuse `uniqdiff` for key presence and duplicate checks;
- it can later feed `uniqreport`.

Initial commands could look like:

```bash
uniqtools rowdiff old.csv new.csv --key id --output changes.jsonl
uniqtools check old.csv new.csv --key id --fail-on removed
uniqtools report changes.jsonl --format html --output report.html
```

The first scaffold step now lives in a separate `uniqtools` repository as
`packages/uniqrowdiff`. The `uniqdiff` repository should keep only engine code,
engine documentation, and small integration examples.

## Compatibility Policy

UniqTools should pin to the stable `uniqdiff` major version:

```toml
uniqdiff>=1.0,<2.0
```

Any behavior needed by tools should be promoted to documented `uniqdiff` public
API before tools rely on it. This keeps the ecosystem stable and prevents product
packages from depending on engine internals.
