import re
from pathlib import Path

import uniqdiff
from uniqdiff._version import __version__

PROJECT_ROOT = Path(__file__).parents[1]

STABLE_ENGINE_EXPORTS = {
    "CompareResult",
    "CompareStats",
    "compare",
    "compare_by_hash",
    "compare_by_key",
    "compare_files",
    "compare_iter",
    "compare_sources",
    "compare_streams",
    "diff",
    "duplicates",
    "duplicates_source",
    "intersection",
    "iter_result_rows",
    "iter_result_values",
    "unique",
}


def test_stable_engine_exports_are_available_from_root_package():
    missing = STABLE_ENGINE_EXPORTS.difference(uniqdiff.__all__)

    assert missing == set()


def test_root_public_api_does_not_export_private_names():
    assert all(not name.startswith("_") for name in uniqdiff.__all__)


def test_public_exports_resolve_to_attributes():
    for name in uniqdiff.__all__:
        assert hasattr(uniqdiff, name)


def test_package_version_constant_matches_pyproject():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)

    assert match is not None
    assert __version__ == match.group(1)
