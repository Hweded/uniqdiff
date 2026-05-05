"""Disk-backed storage backends."""

from uniqdiff.storage.external_sort import compare_external_sort, duplicates_external_sort
from uniqdiff.storage.partition import compare_partitions, duplicates_partitions
from uniqdiff.storage.sqlite import compare_sqlite, duplicates_sqlite

__all__ = [
    "compare_external_sort",
    "compare_partitions",
    "compare_sqlite",
    "duplicates_external_sort",
    "duplicates_partitions",
    "duplicates_sqlite",
]
