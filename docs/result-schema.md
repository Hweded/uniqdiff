# Result Schema

This page documents the stable result schema for `uniqdiff` 1.x.

## `CompareResult`

In memory mode, `compare()` and related helpers return `CompareResult`.

Stable fields:

- `only_in_first`: values found only in the first input;
- `only_in_second`: values found only in the second input;
- `common`: values found in both inputs when requested, otherwise `None`;
- `unique`: combined `only_in_first` and `only_in_second`;
- `duplicates_first`: duplicate values from the first input when requested,
  otherwise `None`;
- `duplicates_second`: duplicate values from the second input when requested,
  otherwise `None`;
- `stats`: `CompareStats`;
- `metadata`: informational backend and connector metadata;
- `warnings`: warning strings.

Minor releases may add metadata fields. They should not remove or rename stable
result fields.

## `CompareStats`

Stable counter fields:

- `first_count`;
- `second_count`;
- `unique_first_count`;
- `unique_second_count`;
- `only_in_first_count`;
- `only_in_second_count`;
- `common_count`;
- `duplicate_first_count`;
- `duplicate_second_count`;
- `mode`;
- `strategy`.

The duplicate counter naming is intentionally singular: each field counts duplicate
rows/items, not duplicate groups.

For the single-source CLI `duplicates --summary` command, the stable counter is:

- `duplicate_count`.

## File Result Rows

`result_mode="file"` writes rows to JSONL or CSV.

Each row has exactly two stable fields:

- `section`;
- `value`.

JSONL example:

```json
{"section": "only_in_first", "value": {"id": "1", "name": "Ann"}}
```

CSV output uses this header:

```text
section,value
```

For CSV, `value` is a JSON-encoded value.

Stable section names:

- `only_in_first`;
- `only_in_second`;
- `common`;
- `duplicates_first`;
- `duplicates_second`.

Consumers should ignore result rows for sections they did not request. Changing the
row field names or the meaning of existing sections is a breaking change.

## Lazy Readers

`iter_result_rows(path, sections=None)` yields dictionaries with `section` and
`value`.

`iter_result_values(path, sections=None)` yields only `value`.

These helpers are the stable way to consume large file-backed outputs.

## Field Diff Result

`compare_fields()`, `compare_fields_files()`, and `compare_file_fields()` return
`FieldDiffResult`.

Stable fields:

- `rows`: changed rows when output is kept in memory;
- `summary_by_column`: changed-field counts by column name;
- `stats`: `FieldDiffStats`;
- `metadata`: field-diff metadata;
- `warnings`: warning strings.

When `output` is provided, changed rows are streamed to JSONL and `rows` stays
empty. Stats and summary are still returned in memory.

## `FieldDiffStats`

Stable counter fields:

- `first_count`;
- `second_count`;
- `compared_count`;
- `changed_row_count`;
- `changed_field_count`;
- `emitted_row_count`;
- `output_bytes`;
- `truncated`.

`changed_row_count` counts all changed matching-key rows found. `emitted_row_count`
counts rows actually written or stored after `max_rows` / `max_bytes` limits.

## Field Diff JSONL Rows

Field-diff JSONL output contains one changed keyed row per line.

Stable fields:

- `key`: comparison key value;
- `changes`: list of changed fields.

Each item in `changes` has:

- `field`;
- `left`;
- `right`.

Example:

```json
{"key":"123","changes":[{"field":"status","left":"draft","right":"active"}]}
```

`iter_field_diff_rows(path)` is the stable lazy reader for field-diff JSONL output.

## Field Diff Duplicate Key Behavior

Field diff indexes the second input by key. If the second input contains duplicate
keys, the first row for that key is used and later rows are ignored for field
comparison.

This behavior is surfaced through:

- `metadata["duplicate_second_key_count"]`;
- a warning when the count is greater than zero.

Changing this default behavior would be a compatibility-affecting change.

## Schema Result

`infer_schema()` returns `SchemaResult`.

Stable fields:

- `columns`: mapping of column name to `ColumnSchema`;
- `row_count`: number of inspected rows;
- `sampled`: whether inference stopped because `sample_size` was reached.

## `ColumnSchema`

Stable fields:

- `name`;
- `types`;
- `nullable`;
- `present_count`;
- `null_count`;
- `missing_count`.

The current inferred type names are:

- `bool`;
- `int`;
- `float`;
- `number` when `strict_numeric_types=False`;
- `str`;
- `list`;
- `tuple`;
- `object`;
- custom class name for other values.

Schema inference is based on observed values. It is not a database DDL parser.

## Schema Diff Result

`compare_schema()` and `compare_file_schema()` return `SchemaDiffResult`.

Stable fields:

- `added_columns`;
- `removed_columns`;
- `type_changes`;
- `nullable_changes`;
- `left_schema`;
- `right_schema`;
- `metadata`;
- `warnings`.

Each `type_changes` item has:

- `column`;
- `left_types`;
- `right_types`.

Each `nullable_changes` item has:

- `column`;
- `left_nullable`;
- `right_nullable`.

The `has_changes` property is true when added columns, removed columns, type
changes, or nullable changes are present.

When `sample_size` is used and at least one input has more rows than the sample,
`warnings` includes:

```text
Schema diff was inferred from sampled rows.
```
