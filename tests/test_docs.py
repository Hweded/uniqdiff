import re
from pathlib import Path

DOCS = Path(__file__).parents[1] / "docs"


def test_docs_index_links_are_not_broken():
    index = DOCS / "README.md"
    content = index.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)

    missing = []
    for link in links:
        if "://" in link or link.startswith("#"):
            continue
        target = (DOCS / link).resolve()
        if not target.exists():
            missing.append(link)

    assert missing == []
