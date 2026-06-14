"""Docs & examples index consistency contract (014): the docs index links every
``docs/*.md`` guide, the examples index lists every ``examples/*.py``, and the
README points at the getting-started guide and the docs index — all checked
against the file tree so no entry is missing or dangling (FR-020-FR-022; SC-005).
"""

from __future__ import annotations

import re

from tests.release_helpers import (
    DOCS,
    EXAMPLES,
    REPO_ROOT,
    docs_guides,
    example_scripts,
)

DOCS_INDEX = DOCS / "README.md"
EXAMPLES_INDEX = EXAMPLES / "README.md"
README = REPO_ROOT / "README.md"

_SIBLING_MD_LINK = re.compile(r"]\(\.?/?([\w-]+\.md)\)")
_EXAMPLE_PATH = re.compile(r"examples/([\w-]+\.py)")


def test_docs_index_links_every_guide() -> None:
    linked = set(_SIBLING_MD_LINK.findall(DOCS_INDEX.read_text(encoding="utf-8")))
    expected = set(docs_guides()) - {"README.md"}
    assert linked == expected, {
        "missing": sorted(expected - linked),
        "dangling": sorted(linked - expected),
    }


def test_examples_index_lists_every_example() -> None:
    listed = set(_EXAMPLE_PATH.findall(EXAMPLES_INDEX.read_text(encoding="utf-8")))
    expected = set(example_scripts())
    assert listed == expected, {
        "missing": sorted(expected - listed),
        "dangling": sorted(listed - expected),
    }


def test_readme_links_getting_started_and_docs_index() -> None:
    text = README.read_text(encoding="utf-8")
    assert "docs/getting-started.md" in text, "README must link getting-started"
    assert "docs/README.md" in text, "README must link the docs index"
    assert (DOCS / "getting-started.md").is_file()
    assert DOCS_INDEX.is_file()
