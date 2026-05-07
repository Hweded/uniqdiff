import uniqdiff
from uniqdiff import engine

ENGINE_CONTRACT_NAMES = {
    "CompareResult",
    "CompareStats",
    "compare",
    "compare_by_hash",
    "compare_by_key",
    "compare_fields",
    "compare_file_fields",
    "compare_file_schema",
    "compare_files",
    "compare_iter",
    "compare_schema",
    "compare_sources",
    "compare_streams",
    "diff",
    "duplicates",
    "duplicates_source",
    "infer_schema",
    "intersection",
    "iter_compare_events",
    "iter_field_diff_rows",
    "iter_result_rows",
    "iter_result_values",
    "iter_sorted_diff",
    "unique",
}


def test_engine_facade_exports_documented_engine_contract_names():
    missing = ENGINE_CONTRACT_NAMES.difference(engine.__all__)

    assert missing == set()


def test_engine_facade_exports_resolve_to_public_attributes():
    for name in engine.__all__:
        assert hasattr(engine, name)


def test_engine_facade_matches_root_public_objects_for_shared_names():
    shared = set(engine.__all__) & set(uniqdiff.__all__)

    for name in shared:
        assert getattr(engine, name) is getattr(uniqdiff, name)


def test_engine_facade_compare_smoke():
    result = engine.compare([1, 2, 3], [2, 3, 4], include_common=True)

    assert result.only_in_first == [1]
    assert result.only_in_second == [4]
    assert result.common == [2, 3]
