"""Changelog & release-readiness contract (014): a Keep a Changelog structure that
covers the shipped layers, and a release-readiness checklist that enumerates the
release gates (FR-041/FR-042; SC-005). Reads the committed tree only.
"""

from __future__ import annotations

import re

from tests.release_helpers import DOCS, REPO_ROOT

CHANGELOG = REPO_ROOT / "CHANGELOG.md"
RELEASE_READINESS = DOCS / "release-readiness.md"


def test_changelog_has_keepachangelog_structure() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.lstrip().startswith("# Changelog"), "missing the # Changelog heading"
    assert re.search(r"^## \[0\.1\.0\]", text, re.MULTILINE), "missing 0.1.0 release"
    assert re.search(r"^### Added", text, re.MULTILINE), "missing an Added section"


def test_changelog_covers_the_shipped_units() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    missing = [f"{unit:03d}" for unit in range(1, 14) if f"{unit:03d}" not in text]
    assert not missing, f"changelog does not mention units: {missing}"


def test_release_readiness_enumerates_the_gates() -> None:
    text = RELEASE_READINESS.read_text(encoding="utf-8").lower()
    for gate in ("build", "gate", "public-saf", "license", "changelog"):
        assert gate in text, f"release-readiness checklist is missing: {gate}"
