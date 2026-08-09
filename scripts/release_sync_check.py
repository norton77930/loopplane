#!/usr/bin/env python
"""Validate that a release tag is synchronized with the repository (unit 082).

Given a ``vX.Y.Z`` ref this script checks the release rules that are
mechanically checkable from the committed tree, per
``docs/architecture/RELEASE_SYNC_RULES.md``:

1. ``__version__`` in ``src/loopplane/__init__.py`` equals the tag's version.
2. ``CHANGELOG.md`` contains a released, validly dated
   ``## [X.Y.Z] - YYYY-MM-DD`` section (``[Unreleased]`` does not count).
3. Every three-digit unit referenced by that section is ``Verified`` on
   ``docs/loopplane-agent-board.md``.

On success the extracted CHANGELOG section is printed to stdout so it can be fed
straight to ``gh release create --notes-file``; diagnostics always go to stderr,
so stdout stays clean for the notes. Any failure exits non-zero with one line per
problem, and the release workflow stops before building or publishing anything.

The remaining release-sync rules (api-reference / capabilities / gap-analysis
currency and ADR references) stay in the human runbook,
``docs/release-process.md``.

Standard library only, offline, and deliberately free of any ``loopplane``
import: it must run in a checkout before the project is installed.

Usage:

    python scripts/release_sync_check.py v0.5.0
    python scripts/release_sync_check.py refs/tags/v0.5.0 --notes-file notes.md
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO

TAG_PATTERN = re.compile(r"^(?:refs/tags/)?v(\d+\.\d+\.\d+)$")
VERSION_PATTERN = re.compile(
    r"^__version__\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)
BOLD_UNIT_PATTERN = re.compile(r"\*\*(\d{3})\*\*")
NAMED_UNIT_LINE_PATTERN = re.compile(r"^.*\bunits?\b.*$", re.IGNORECASE | re.MULTILINE)
THREE_DIGIT_PATTERN = re.compile(r"(?<!\d)(\d{3})(?!\d)")
BOARD_ROW_PATTERN = re.compile(
    r"^\|\s+\*\*(?P<unit>\d{3})-[^*]+\*\*\s+\|[^|]*\|"
    r"\s+\*\*(?P<status>[^*]+)\*\*\s+\|",
    re.MULTILINE,
)

VERSION_FILE = Path("src") / "loopplane" / "__init__.py"
CHANGELOG_FILE = Path("CHANGELOG.md")
BOARD_FILE = Path("docs") / "loopplane-agent-board.md"

RUNBOOK_REMINDER = (
    "Reminder - the non-mechanical release-sync checks stay with the human "
    "runbook\n(docs/release-process.md, "
    "docs/architecture/RELEASE_SYNC_RULES.md):\n"
    "docs/api-reference.md + capabilities + gap-analysis currency, and the ADR "
    "references\nof the CHANGELOG section."
)


@dataclass(frozen=True)
class ReleaseSyncResult:
    """The outcome of the mechanical release-sync checks for one tag."""

    tag: str
    version: str
    init_version_ok: bool
    changelog_section_ok: bool
    board_status_ok: bool
    notes: str
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def parse_tag(ref: str) -> str:
    """Return ``X.Y.Z`` for a ``vX.Y.Z`` (or ``refs/tags/vX.Y.Z``) ref.

    Anything else is refused: the release path is deliberately narrow, so a
    branch name, a pre-release suffix, or a partial version cannot start a
    release run.
    """

    match = TAG_PATTERN.match(ref.strip())
    if match is None:
        raise ValueError(
            f"{ref!r} is not a release tag; expected the vX.Y.Z form "
            "(for example v0.5.0)"
        )
    return match.group(1)


def read_declared_version(repo_root: Path) -> str | None:
    """The ``__version__`` literal declared in the package, or None."""

    path = repo_root / VERSION_FILE
    if not path.is_file():
        return None
    match = VERSION_PATTERN.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def extract_changelog_section(text: str, version: str) -> str | None:
    """The released ``## [version] - date`` section of a changelog, or None.

    The section must carry a date: an entry that is still ``[Unreleased]`` or a
    heading without a date is not a released section, so it must not be able to
    authorize a publish.
    """

    heading = re.compile(
        r"^##\s+\[" + re.escape(version) + r"\]\s+-\s+(?P<date>\d{4}-\d{2}-\d{2})\s*$",
        re.MULTILINE,
    )
    match = heading.search(text)
    if match is None:
        return None
    try:
        date.fromisoformat(match.group("date"))
    except ValueError:
        return None
    rest = text[match.end() :]
    next_heading = re.search(r"^##\s", rest, re.MULTILINE)
    body = rest[: next_heading.start()] if next_heading else rest
    return (match.group(0) + body).rstrip() + "\n"


def release_units(notes: str) -> tuple[str, ...]:
    """Three-digit unit ids referenced by a released CHANGELOG section."""

    units = list(BOLD_UNIT_PATTERN.findall(notes))
    for match in NAMED_UNIT_LINE_PATTERN.finditer(notes):
        units.extend(THREE_DIGIT_PATTERN.findall(match.group(0)))
    return tuple(dict.fromkeys(units))


def read_board_statuses(repo_root: Path) -> dict[str, str] | None:
    """Map board unit ids to their live statuses, or None when the board is absent."""

    path = repo_root / BOARD_FILE
    if not path.is_file():
        return None
    return {
        match.group("unit"): match.group("status").strip()
        for match in BOARD_ROW_PATTERN.finditer(path.read_text(encoding="utf-8"))
    }


def check_release_sync(ref: str, repo_root: Path) -> ReleaseSyncResult:
    """Run every mechanical check for ``ref`` against the tree at ``repo_root``."""

    version = parse_tag(ref)
    failures: list[str] = []

    declared = read_declared_version(repo_root)
    init_version_ok = declared == version
    if declared is None:
        failures.append(
            f"{VERSION_FILE.as_posix()} declares no __version__ "
            f"(expected {version} for tag {ref})"
        )
    elif not init_version_ok:
        failures.append(
            f"{VERSION_FILE.as_posix()} __version__ is {declared}, "
            f"expected {version} for tag {ref}"
        )

    changelog_path = repo_root / CHANGELOG_FILE
    notes = ""
    if not changelog_path.is_file():
        failures.append(f"{CHANGELOG_FILE.as_posix()} is missing")
    else:
        section = extract_changelog_section(
            changelog_path.read_text(encoding="utf-8"), version
        )
        if section is None:
            failures.append(
                f"{CHANGELOG_FILE.as_posix()} has no released, dated section "
                f"[{version}] (promote [Unreleased] first)"
            )
        else:
            notes = section

    board_status_ok = False
    if notes:
        units = release_units(notes)
        statuses = read_board_statuses(repo_root)
        if not units:
            failures.append(
                f"{CHANGELOG_FILE.as_posix()} release section [{version}] has no "
                "three-digit unit reference"
            )
        elif statuses is None:
            failures.append(f"{BOARD_FILE.as_posix()} is missing")
        else:
            board_failures = 0
            for unit in units:
                status = statuses.get(unit)
                if status is None:
                    failures.append(
                        f"release unit {unit} is missing from {BOARD_FILE.as_posix()}"
                    )
                    board_failures += 1
                elif status != "Verified":
                    failures.append(
                        f"release unit {unit} has board status {status!r}, expected "
                        "'Verified'"
                    )
                    board_failures += 1
            board_status_ok = board_failures == 0

    return ReleaseSyncResult(
        tag=ref,
        version=version,
        init_version_ok=init_version_ok,
        changelog_section_ok=bool(notes),
        board_status_ok=board_status_ok,
        notes=notes,
        failures=tuple(failures),
    )


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_sync_check.py",
        description="Fail closed unless a vX.Y.Z tag is synchronized with "
        "__version__, a dated CHANGELOG section, and Verified board units.",
    )
    parser.add_argument("tag", help="the release ref, e.g. v0.5.0")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repository root to inspect (default: this script's repository)",
    )
    parser.add_argument(
        "--notes-file",
        type=Path,
        default=None,
        help="also write the extracted CHANGELOG section to this file",
    )
    args = parser.parse_args(argv)

    out: TextIO = sys.stdout
    err: TextIO = sys.stderr
    repo_root = args.repo_root or _default_repo_root()

    try:
        result = check_release_sync(args.tag, repo_root)
    except ValueError as exc:
        print(f"[fail] {exc}", file=err)
        print(
            "FAIL: refusing to run release checks for a non-release ref; "
            "nothing may be published.",
            file=err,
        )
        return 2

    print(f"[ok] tag {result.tag} -> version {result.version}", file=err)
    if result.init_version_ok:
        print(
            f"[ok] {VERSION_FILE.as_posix()} __version__ == {result.version}",
            file=err,
        )
    if result.changelog_section_ok:
        print(
            f"[ok] {CHANGELOG_FILE.as_posix()} section "
            f"[{result.version}] found and validly dated",
            file=err,
        )
    if result.board_status_ok:
        print(
            f"[ok] every released unit is Verified on {BOARD_FILE.as_posix()}",
            file=err,
        )
    for failure in result.failures:
        print(f"[fail] {failure}", file=err)

    if not result.ok:
        print(
            f"FAIL: {len(result.failures)} release-sync check(s) failed for "
            f"{result.tag}; nothing may be published.",
            file=err,
        )
        print(RUNBOOK_REMINDER, file=err)
        return 1

    print(f"PASS: release sync checks passed for {result.tag}", file=err)
    print(RUNBOOK_REMINDER, file=err)

    if args.notes_file is not None:
        args.notes_file.write_text(result.notes, encoding="utf-8")
    out.write(result.notes)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
