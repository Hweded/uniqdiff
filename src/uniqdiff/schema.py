"""Schema inference and schema-aware diff helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Optional

from uniqdiff.exceptions import InvalidInputError
from uniqdiff.io.readers import read_file


@dataclass(frozen=True)
class ColumnSchema:
    """Inferred schema for one column."""

    name: str
    types: tuple[str, ...]
    nullable: bool
    present_count: int
    null_count: int
    missing_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "types": list(self.types),
            "nullable": self.nullable,
            "present_count": self.present_count,
            "null_count": self.null_count,
            "missing_count": self.missing_count,
        }


@dataclass(frozen=True)
class SchemaResult:
    """Schema inferred from structured rows."""

    columns: dict[str, ColumnSchema] = field(default_factory=dict)
    row_count: int = 0
    sampled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": {name: schema.to_dict() for name, schema in sorted(self.columns.items())},
            "row_count": self.row_count,
            "sampled": self.sampled,
        }


@dataclass(frozen=True)
class SchemaDiffResult:
    """Difference between two inferred schemas."""

    added_columns: list[str] = field(default_factory=list)
    removed_columns: list[str] = field(default_factory=list)
    type_changes: list[dict[str, Any]] = field(default_factory=list)
    nullable_changes: list[dict[str, Any]] = field(default_factory=list)
    left_schema: SchemaResult = field(default_factory=SchemaResult)
    right_schema: SchemaResult = field(default_factory=SchemaResult)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added_columns": self.added_columns,
            "removed_columns": self.removed_columns,
            "type_changes": self.type_changes,
            "nullable_changes": self.nullable_changes,
            "left_schema": self.left_schema.to_dict(),
            "right_schema": self.right_schema.to_dict(),
            "metadata": self.metadata,
            "warnings": self.warnings,
        }

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_columns or self.removed_columns or self.type_changes or self.nullable_changes
        )


def infer_schema(
    rows: Iterable[Any],
    *,
    sample_size: Optional[int] = None,
    empty_string_null: bool = True,
    strict_numeric_types: bool = True,
) -> SchemaResult:
    """Infer simple column names, value types, and nullability from structured rows."""

    if sample_size is not None and sample_size < 0:
        raise InvalidInputError("sample_size must be greater than or equal to zero")

    trackers: dict[str, _ColumnTracker] = {}
    row_count = 0
    sampled = False

    for row in rows:
        if sample_size is not None and row_count >= sample_size:
            sampled = True
            break

        mapping = _as_mapping(row)
        row_fields = set(mapping)
        for name in row_fields:
            trackers.setdefault(name, _ColumnTracker(name=name))
        for name in set(trackers) - row_fields:
            trackers[name].missing_count += 1
        for name, value in mapping.items():
            trackers[name].record(
                value,
                empty_string_null=empty_string_null,
                strict_numeric_types=strict_numeric_types,
            )
        row_count += 1

    return SchemaResult(
        columns={name: tracker.to_schema() for name, tracker in trackers.items()},
        row_count=row_count,
        sampled=sampled,
    )


def compare_schema(
    first: Iterable[Any],
    second: Iterable[Any],
    *,
    sample_size: Optional[int] = None,
    empty_string_null: bool = True,
    strict_numeric_types: bool = True,
) -> SchemaDiffResult:
    """Infer and compare schemas for two structured inputs."""

    left = infer_schema(
        first,
        sample_size=sample_size,
        empty_string_null=empty_string_null,
        strict_numeric_types=strict_numeric_types,
    )
    right = infer_schema(
        second,
        sample_size=sample_size,
        empty_string_null=empty_string_null,
        strict_numeric_types=strict_numeric_types,
    )
    return _diff_schemas(
        left,
        right,
        metadata={
            "sample_size": sample_size,
            "empty_string_null": empty_string_null,
            "strict_numeric_types": strict_numeric_types,
        },
    )


def compare_file_schema(
    file_a: str,
    file_b: str,
    *,
    format: str = "auto",
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
    quotechar: Optional[str] = '"',
    has_header: bool = True,
    fieldnames: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    batch_size: int = 65_536,
    sample_size: Optional[int] = None,
    empty_string_null: bool = True,
    strict_numeric_types: bool = True,
) -> SchemaDiffResult:
    """Read supported files and compare their inferred schemas."""

    first = read_file(
        file_a,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=columns,
        batch_size=batch_size,
    )
    second = read_file(
        file_b,
        format=format,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        has_header=has_header,
        fieldnames=fieldnames,
        columns=columns,
        batch_size=batch_size,
    )
    result = compare_schema(
        first,
        second,
        sample_size=sample_size,
        empty_string_null=empty_string_null,
        strict_numeric_types=strict_numeric_types,
    )
    result.metadata["format"] = format
    result.metadata["columns"] = list(columns) if columns is not None else None
    return result


@dataclass
class _ColumnTracker:
    name: str
    types: set[str] = field(default_factory=set)
    present_count: int = 0
    null_count: int = 0
    missing_count: int = 0

    def record(
        self,
        value: Any,
        *,
        empty_string_null: bool,
        strict_numeric_types: bool,
    ) -> None:
        self.present_count += 1
        if _is_null(value, empty_string_null=empty_string_null):
            self.null_count += 1
            return
        self.types.add(_type_name(value, strict_numeric_types=strict_numeric_types))

    def to_schema(self) -> ColumnSchema:
        return ColumnSchema(
            name=self.name,
            types=tuple(sorted(self.types)),
            nullable=self.null_count > 0 or self.missing_count > 0,
            present_count=self.present_count,
            null_count=self.null_count,
            missing_count=self.missing_count,
        )


def _diff_schemas(
    left: SchemaResult,
    right: SchemaResult,
    *,
    metadata: dict[str, Any],
) -> SchemaDiffResult:
    left_names = set(left.columns)
    right_names = set(right.columns)
    common = sorted(left_names & right_names)

    type_changes = []
    nullable_changes = []
    for name in common:
        left_column = left.columns[name]
        right_column = right.columns[name]
        if left_column.types != right_column.types:
            type_changes.append(
                {
                    "column": name,
                    "left_types": list(left_column.types),
                    "right_types": list(right_column.types),
                }
            )
        if left_column.nullable != right_column.nullable:
            nullable_changes.append(
                {
                    "column": name,
                    "left_nullable": left_column.nullable,
                    "right_nullable": right_column.nullable,
                }
            )

    warnings = []
    if left.sampled or right.sampled:
        warnings.append("Schema diff was inferred from sampled rows.")

    return SchemaDiffResult(
        added_columns=sorted(right_names - left_names),
        removed_columns=sorted(left_names - right_names),
        type_changes=type_changes,
        nullable_changes=nullable_changes,
        left_schema=left,
        right_schema=right,
        metadata=metadata,
        warnings=warnings,
    )


def _as_mapping(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row
    if is_dataclass(row) and not isinstance(row, type):
        return asdict(row)
    values = getattr(row, "__dict__", None)
    if isinstance(values, Mapping):
        return values
    raise InvalidInputError("schema inference requires dict-like, dataclass, or object rows")


def _is_null(value: Any, *, empty_string_null: bool) -> bool:
    return value is None or (empty_string_null and value == "")


def _type_name(value: Any, *, strict_numeric_types: bool) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int" if strict_numeric_types else "number"
    if isinstance(value, float):
        return "float" if strict_numeric_types else "number"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__
