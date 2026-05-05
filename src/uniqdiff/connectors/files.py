"""Built-in file source connectors."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Optional, Union

from uniqdiff.io.readers import read_csv, read_file, read_jsonl, read_parquet, read_text, read_tsv


class FileConnector:
    """Connector that reads a supported file format."""

    name = "file"

    def __init__(
        self,
        source: Union[str, Path],
        *,
        format: str = "auto",
        encoding: str = "utf-8",
        delimiter: Optional[str] = None,
        quotechar: Optional[str] = '"',
        has_header: bool = True,
        fieldnames: Optional[Sequence[str]] = None,
        columns: Optional[Sequence[str]] = None,
        batch_size: int = 65_536,
    ) -> None:
        self.source = Path(source)
        self.format = format
        self.encoding = encoding
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.has_header = has_header
        self.fieldnames = tuple(fieldnames) if fieldnames is not None else None
        self.columns = tuple(columns) if columns is not None else None
        self.batch_size = batch_size

    def open(self) -> Iterator[Any]:
        return read_file(
            self.source,
            format=self.format,
            encoding=self.encoding,
            delimiter=self.delimiter,
            quotechar=self.quotechar,
            has_header=self.has_header,
            fieldnames=self.fieldnames,
            columns=self.columns,
            batch_size=self.batch_size,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "connector": self.name,
            "path": str(self.source),
            "format": self.format,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "has_header": self.has_header,
            "fieldnames": self.fieldnames,
            "columns": self.columns,
            "batch_size": self.batch_size,
        }


class CSVConnector(FileConnector):
    """Connector for CSV files."""

    name = "csv"

    def __init__(
        self,
        source: Union[str, Path],
        *,
        encoding: str = "utf-8",
        delimiter: str = ",",
        quotechar: Optional[str] = '"',
        has_header: bool = True,
        fieldnames: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(
            source,
            format="csv",
            encoding=encoding,
            delimiter=delimiter,
            quotechar=quotechar,
            has_header=has_header,
            fieldnames=fieldnames,
        )

    def open(self) -> Iterator[Any]:
        return read_csv(
            self.source,
            encoding=self.encoding,
            delimiter="," if self.delimiter is None else self.delimiter,
            quotechar=self.quotechar,
            has_header=self.has_header,
            fieldnames=self.fieldnames,
        )


class JSONLConnector(FileConnector):
    """Connector for JSON Lines files."""

    name = "jsonl"

    def __init__(self, source: Union[str, Path], *, encoding: str = "utf-8") -> None:
        super().__init__(source, format="jsonl", encoding=encoding)

    def open(self) -> Iterator[Any]:
        return read_jsonl(self.source, encoding=self.encoding)


class TSVConnector(FileConnector):
    """Connector for TSV files."""

    name = "tsv"

    def __init__(
        self,
        source: Union[str, Path],
        *,
        encoding: str = "utf-8",
        delimiter: str = "\t",
        quotechar: Optional[str] = '"',
        has_header: bool = True,
        fieldnames: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(
            source,
            format="tsv",
            encoding=encoding,
            delimiter=delimiter,
            quotechar=quotechar,
            has_header=has_header,
            fieldnames=fieldnames,
        )

    def open(self) -> Iterator[Any]:
        return read_tsv(
            self.source,
            encoding=self.encoding,
            delimiter="\t" if self.delimiter is None else self.delimiter,
            quotechar=self.quotechar,
            has_header=self.has_header,
            fieldnames=self.fieldnames,
        )


class ParquetConnector(FileConnector):
    """Connector for Parquet files using optional pyarrow."""

    name = "parquet"

    def __init__(
        self,
        source: Union[str, Path],
        *,
        columns: Optional[Sequence[str]] = None,
        batch_size: int = 65_536,
    ) -> None:
        super().__init__(
            source,
            format="parquet",
            columns=columns,
            batch_size=batch_size,
        )

    def open(self) -> Iterator[dict[str, Any]]:
        return read_parquet(
            self.source,
            columns=self.columns,
            batch_size=self.batch_size,
        )


class TextConnector(FileConnector):
    """Connector for text files."""

    name = "txt"

    def __init__(self, source: Union[str, Path], *, encoding: str = "utf-8") -> None:
        super().__init__(source, format="txt", encoding=encoding)

    def open(self) -> Iterator[str]:
        return read_text(self.source, encoding=self.encoding)
