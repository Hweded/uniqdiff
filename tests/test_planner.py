import pytest

from uniqdiff import InvalidInputError
from uniqdiff.planner import (
    auto_decision_for_sources,
    build_execution_plan,
    ensure_disk_strategy,
)


def test_ensure_disk_strategy_accepts_aliases():
    assert ensure_disk_strategy("partition") == "hash_partition"
    assert ensure_disk_strategy("external-sort") == "external_sort"


def test_ensure_disk_strategy_rejects_unknown_value():
    with pytest.raises(InvalidInputError):
        ensure_disk_strategy("unknown")


def test_auto_decision_uses_memory_when_estimate_fits_limit():
    decision = auto_decision_for_sources(
        [1, 2],
        [2, 3],
        memory_limit="1MB",
        temp_dir=None,
        result_mode="memory",
    )

    assert decision["use_disk"] is False
    assert decision["selected_backend"] == "memory"
    assert decision["effective_memory_limit_bytes"] > 0


def test_auto_decision_uses_disk_for_file_result_mode():
    decision = auto_decision_for_sources(
        [1],
        [2],
        memory_limit=None,
        temp_dir=None,
        result_mode="file",
    )

    assert decision["use_disk"] is True
    assert decision["reason"] == "result_mode='file'"


def test_build_execution_plan_rejects_file_result_without_output():
    with pytest.raises(InvalidInputError):
        build_execution_plan(
            [1],
            [2],
            mode="disk",
            result_mode="file",
            disk_strategy="sqlite",
            partition_count=None,
            memory_limit=None,
            temp_dir=None,
            disk_limit=None,
            chunk_size=1000,
            output=None,
            preserve_order=True,
        )


def test_build_execution_plan_records_metadata():
    plan = build_execution_plan(
        [1],
        [2],
        mode="auto",
        result_mode="memory",
        disk_strategy="hash",
        partition_count=8,
        memory_limit="1B",
        temp_dir=None,
        disk_limit="1GB",
        chunk_size=10,
        output=None,
        preserve_order=False,
    )

    assert plan.use_disk is True
    assert plan.disk_strategy == "hash_partition"
    assert plan.partition_count == 8
    assert plan.metadata["preserve_order"] is False
    assert plan.metadata["auto_decision"]["selected_backend"] == "disk"
