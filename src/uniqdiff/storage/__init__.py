"""Disk-backed storage backends."""

from uniqdiff.storage.external_sort import compare_external_sort, duplicates_external_sort
from uniqdiff.storage.memory import compare_memory, duplicates_memory
from uniqdiff.storage.partition import compare_partitions, duplicates_partitions
from uniqdiff.storage.protocols import CompareBackend, DuplicatesBackend
from uniqdiff.storage.sqlite import compare_sqlite, duplicates_sqlite

__all__ = [
    "CompareBackend",
    "DuplicatesBackend",
    "compare_external_sort",
    "compare_memory",
    "compare_partitions",
    "compare_sqlite",
    "duplicates_external_sort",
    "duplicates_memory",
    "duplicates_partitions",
    "duplicates_sqlite",
]
