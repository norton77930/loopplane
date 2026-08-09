"""Release-sync validator contract (082, US2): the tag a maintainer pushes must
agree with ``loopplane.__version__`` and with a dated ``CHANGELOG.md`` section
before anything is built or published (FR-004; SC-002).

Written test-first, against ``scripts/release_sync_check.py``. The script is
loaded by path (``scripts/`` is not an importable package) and must stay
standard-library only and offline, so the release workflow can run it before any
environment is installed.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "release_sync_check.py"

STDLIB_ALLOWED = {
    "__future__",
    "argparse",
    "dataclasses",
    "datetime",
    "pathlib",
    "re",
    "sys",
    "collections",
    "collections.abc",
    "typing",
}


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_sync_check", SCRIPT)
    assert spec is not None and spec.loader is not None, SCRIPT
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_script()


def _write_repo(
    root: Path,
    *,
    version: str,
    changelog: str,
    board_status: str = "Verified",
) -> Path:
    package = root / "src" / "loopplane"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        f'"""Fixture package."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "loopplane-agent-board.md").write_text(
        "| Unit | Spec Directory | Status | Scope | Depends On | Next Action |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| **001-fixture** | `specs/001-fixture` | **{board_status}** | "
        "fixture | — | — |\n",
        encoding="utf-8",
    )
    return root


DATED_CHANGELOG = """# Changelog

## [Unreleased]

- work in flight

## [1.2.3] - 2026-01-31

### Added

- **001** the thing that shipped

## [1.2.2] - 2026-01-01

- the previous thing
"""


# --- tag parsing ---------------------------------------------------------


def test_parse_tag_accepts_plain_and_ref_forms() -> None:
    assert checker.parse_tag("v1.2.3") == "1.2.3"
    assert checker.parse_tag("refs/tags/v1.2.3") == "1.2.3"


@pytest.mark.parametrize(
    "ref",
    ["1.2.3", "v1.2", "v1.2.3.4", "vX.Y.Z", "release-1.2.3", "v1.2.3-rc1", ""],
)
def test_parse_tag_rejects_anything_but_vmajor_minor_patch(ref: str) -> None:
    with pytest.raises(ValueError):
        checker.parse_tag(ref)


# --- changelog extraction ------------------------------------------------


def test_extract_changelog_section_returns_the_dated_section() -> None:
    section = checker.extract_changelog_section(DATED_CHANGELOG, "1.2.3")
    assert section is not None
    assert section.startswith("## [1.2.3] - 2026-01-31")
    assert "the thing that shipped" in section
    assert "the previous thing" not in section, "must stop at the next section"


def test_extract_changelog_section_requires_a_date() -> None:
    undated = "# Changelog\n\n## [1.2.3]\n\n- undated\n"
    assert checker.extract_changelog_section(undated, "1.2.3") is None


def test_extract_changelog_section_rejects_an_invalid_calendar_date() -> None:
    invalid = "# Changelog\n\n## [1.2.3] - 2026-99-99\n\n- **001** bad date\n"
    assert checker.extract_changelog_section(invalid, "1.2.3") is None


def test_extract_changelog_section_ignores_unreleased() -> None:
    assert checker.extract_changelog_section(DATED_CHANGELOG, "9.9.9") is None
    assert "Unreleased" not in (
        checker.extract_changelog_section(DATED_CHANGELOG, "1.2.3") or ""
    )


# --- end-to-end checks ---------------------------------------------------


def test_check_passes_against_the_current_tree() -> None:
    declared = checker.read_declared_version(REPO_ROOT)
    result = checker.check_release_sync(f"v{declared}", REPO_ROOT)
    assert result.ok, result.failures
    assert result.init_version_ok
    assert result.changelog_section_ok
    assert result.board_status_ok
    assert result.notes.startswith(f"## [{declared}]")


def test_check_fails_when_a_released_unit_is_not_verified(tmp_path: Path) -> None:
    root = _write_repo(
        tmp_path,
        version="1.2.3",
        changelog=DATED_CHANGELOG,
        board_status="Implementation in progress",
    )
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.board_status_ok
    assert len(result.failures) == 1
    assert "001" in result.failures[0]
    assert "Implementation in progress" in result.failures[0]


def test_check_fails_for_an_explicit_unit_reference_outside_bold_bullet_form(
    tmp_path: Path,
) -> None:
    changelog = DATED_CHANGELOG.replace(
        "- **001** the thing that shipped",
        "- Unit 002 shipped",
    )
    root = _write_repo(tmp_path, version="1.2.3", changelog=changelog)
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.board_status_ok
    assert "002" in result.failures[0]
    assert "missing" in result.failures[0]


def test_check_fails_when_one_of_multiple_named_units_is_missing(
    tmp_path: Path,
) -> None:
    changelog = DATED_CHANGELOG.replace(
        "- **001** the thing that shipped",
        "- Units 001 and 002 shipped",
    )
    root = _write_repo(tmp_path, version="1.2.3", changelog=changelog)
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.board_status_ok
    assert any("002" in failure and "missing" in failure for failure in result.failures)


def test_check_fails_when_release_notes_name_no_unit(tmp_path: Path) -> None:
    changelog = DATED_CHANGELOG.replace(
        "- **001** the thing that shipped",
        "- maintenance release",
    )
    root = _write_repo(tmp_path, version="1.2.3", changelog=changelog)
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.board_status_ok
    assert "no three-digit unit reference" in result.failures[0]


def test_check_fails_when_a_released_unit_is_missing_from_the_board(
    tmp_path: Path,
) -> None:
    root = _write_repo(tmp_path, version="1.2.3", changelog=DATED_CHANGELOG)
    (root / "docs" / "loopplane-agent-board.md").write_text(
        "| Unit | Spec Directory | Status | Scope | Depends On | Next Action |\n"
        "| --- | --- | --- | --- | --- | --- |\n",
        encoding="utf-8",
    )
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.board_status_ok
    assert "001" in result.failures[0]
    assert "missing" in result.failures[0]


def test_check_reports_a_version_mismatch(tmp_path: Path) -> None:
    root = _write_repo(tmp_path, version="1.2.2", changelog=DATED_CHANGELOG)
    result = checker.check_release_sync("v1.2.3", root)
    assert not result.ok
    assert not result.init_version_ok
    assert result.changelog_section_ok
    assert len(result.failures) == 1
    assert "1.2.2" in result.failures[0] and "1.2.3" in result.failures[0]


def test_check_reports_a_missing_changelog_section(tmp_path: Path) -> None:
    root = _write_repo(tmp_path, version="9.9.9", changelog=DATED_CHANGELOG)
    result = checker.check_release_sync("v9.9.9", root)
    assert not result.ok
    assert result.init_version_ok
    assert not result.changelog_section_ok
    assert len(result.failures) == 1
    assert "9.9.9" in result.failures[0]


def test_check_reports_one_line_per_failure(tmp_path: Path) -> None:
    root = _write_repo(tmp_path, version="1.2.2", changelog=DATED_CHANGELOG)
    result = checker.check_release_sync("v9.9.9", root)
    assert not result.ok
    assert len(result.failures) == 2
    assert all("\n" not in failure for failure in result.failures)


# --- command-line behavior ----------------------------------------------


def test_main_exits_zero_and_prints_the_notes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _write_repo(tmp_path, version="1.2.3", changelog=DATED_CHANGELOG)
    code = checker.main(["v1.2.3", "--repo-root", str(root)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.startswith("## [1.2.3] - 2026-01-31")
    assert "the thing that shipped" in captured.out


def test_main_exits_non_zero_and_diagnoses_each_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _write_repo(tmp_path, version="1.2.2", changelog=DATED_CHANGELOG)
    code = checker.main(["v9.9.9", "--repo-root", str(root)])
    captured = capsys.readouterr()
    assert code != 0
    assert captured.out == "", "no release notes may be emitted on failure"
    assert captured.err.count("[fail]") == 2
    assert "nothing may be published" in captured.err


def test_main_rejects_a_non_release_ref(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = checker.main(["main", "--repo-root", str(REPO_ROOT)])
    captured = capsys.readouterr()
    assert code != 0
    assert captured.out == ""
    assert "vX.Y.Z" in captured.err


def test_main_writes_the_notes_file_for_the_release_job(tmp_path: Path) -> None:
    root = _write_repo(tmp_path, version="1.2.3", changelog=DATED_CHANGELOG)
    notes = tmp_path / "release-notes.md"
    code = checker.main(
        ["v1.2.3", "--repo-root", str(root), "--notes-file", str(notes)]
    )
    assert code == 0
    assert notes.read_text(encoding="utf-8").startswith("## [1.2.3]")


def test_failure_help_names_the_human_runbook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _write_repo(tmp_path, version="1.2.2", changelog=DATED_CHANGELOG)
    checker.main(["v9.9.9", "--repo-root", str(root)])
    err = capsys.readouterr().err
    assert "docs/release-process.md" in err
    assert "RELEASE_SYNC_RULES.md" in err


# --- script hygiene ------------------------------------------------------


def test_script_imports_only_the_standard_library() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    unexpected = {name for name in imported if name not in STDLIB_ALLOWED}
    assert not unexpected, f"release_sync_check must stay stdlib-only: {unexpected}"


def test_script_never_imports_the_product_package() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "import loopplane" not in text, (
        "the validator must read __version__ textually so it runs before install"
    )
