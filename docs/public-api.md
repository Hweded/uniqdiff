# Public API Boundary

This page defines the public module boundary for `uniqdiff` 1.x.

The preferred public import path is the root package:

```python
from uniqdiff import compare, CompareResult, iter_result_values
```

## Stable Root Exports

The following names are part of the 1.x engine contract:

- `compare`;
- `diff`;
- `unique`;
- `intersection`;
- `duplicates`;
- `compare_by_key`;
- `compare_by_hash`;
- `compare_iter`;
- `compare_sorted_iter`;
- `compare_streams`;
- `compare_files`;
- `compare_sources`;
- `duplicates_source`;
- `iter_compare_events`;
- `iter_field_diff_events`;
- `iter_sorted_field_diff_events`;
- `compare_fields`;
- `compare_fields_sorted`;
- `iter_field_diff_sorted`;
- `compare_fields_files`;
- `compare_fields_files_sorted`;
- `compare_file_fields`;
- `compare_file_fields_sorted`;
- `iter_field_diff_rows`;
- `iter_event_rows`;
- `summarize_events`;
- `summarize_event_file`;
- `infer_schema`;
- `compare_schema`;
- `compare_file_schema`;
- `CompareResult`;
- `CompareStats`;
- `iter_result_rows`;
- `iter_result_values`;
- `iter_sorted_diff`;
- `write_sorted_diff`;
- `write_sorted_diff_file`;
- connector protocol and registry helpers;
- built-in local connectors;
- documented exception classes.

These names should not be removed or renamed in a minor release.

## Public Modules

These modules may be imported directly when users need a narrower namespace:

- `uniqdiff`: preferred stable facade;
- `uniqdiff.connectors`: connector protocol, built-in connectors, registry helpers;
- `uniqdiff.exceptions`: documented exception classes;
- `uniqdiff.normalizers`: built-in normalizer helpers;
- `uniqdiff.output`: JSONL event writers, event schema helpers, and lazy result readers;
- `uniqdiff.result`: result dataclasses;
- `uniqdiff.fields`: field-level diff dataclasses and helpers;
- `uniqdiff.schema`: schema inference and schema diff dataclasses and helpers;
- `uniqdiff.io`: low-level local file readers;
- `uniqdiff.bloom`: probabilistic helper API;
- `uniqdiff.fuzzy`: approximate string helper API.

`uniqdiff.bloom` and `uniqdiff.fuzzy` are public helper modules, but they are not part
of the exact comparison semantics. They must remain clearly documented as
probabilistic or approximate.

## Internal Modules

These modules are implementation details and are not covered by the 1.x compatibility
contract:

- modules whose name starts with `_`, such as `uniqdiff._utils` and `uniqdiff._typing`;
- `uniqdiff.cli`;
- `uniqdiff.core`;
- `uniqdiff.disk`;
- `uniqdiff.storage`;
- `uniqdiff.strategies`;
- individual backend modules under `uniqdiff.storage`.

Downstream tools should not depend on these modules directly. If a downstream tool
needs behavior that currently exists only in an internal module, promote a small,
documented wrapper through the public facade instead of importing the internal module.

## Compatibility Rule

Compatibility is defined by documented behavior, root exports, result schemas, CLI
contracts, and documented module APIs. Internal modules may change in minor releases
as long as the public engine contract remains stable.
