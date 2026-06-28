"""Audit Spec Kit task checkboxes against the roadmap board.

The board is the authoritative roadmap status, but historical features may have
unchecked task boxes from early autopilot runs. Those exceptions must be
explicit and durable so future agents do not mistake legacy drift for current
unfinished work.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "docs" / "loopplane-agent-board.md"
EXCEPTIONS = ROOT / "docs" / "spec-task-audit-exceptions.md"
SPECS = ROOT / "specs"

TASK_RE = re.compile(r"^- \[[ xX]\]")
UNCHECKED_RE = re.compile(r"^- \[ \]")
VERIFIED_ROW_RE = re.compile(
    r"^\|\s+\*\*(?P<unit>\d{3}-[a-z0-9-]+)\*\*.*\|\s+\*\*Verified\*\*\s+\|"
)
EXCEPTION_RE = re.compile(r"`specs/(?P<unit>\d{3}-[a-z0-9-]+)`")


def _verified_units() -> set[str]:
    return {
        match.group("unit")
        for line in BOARD.read_text(encoding="utf-8").splitlines()
        if (match := VERIFIED_ROW_RE.search(line))
    }


def _unchecked_count(unit: str) -> int:
    tasks = SPECS / unit / "tasks.md"
    if not tasks.exists():
        return 0
    return sum(
        1
        for line in tasks.read_text(encoding="utf-8").splitlines()
        if TASK_RE.search(line) and UNCHECKED_RE.search(line)
    )


def _exception_units() -> set[str]:
    if not EXCEPTIONS.exists():
        return set()
    return {
        match.group("unit")
        for line in EXCEPTIONS.read_text(encoding="utf-8").splitlines()
        if (match := EXCEPTION_RE.search(line))
    }


def test_verified_specs_with_unchecked_tasks_are_explicitly_excepted() -> None:
    verified = _verified_units()
    exceptions = _exception_units()

    drift = {
        unit: count
        for unit in sorted(verified)
        if (count := _unchecked_count(unit)) > 0
    }
    unapproved = {
        unit: count for unit, count in drift.items() if unit not in exceptions
    }
    stale_exceptions = sorted(unit for unit in exceptions if unit not in drift)

    assert not unapproved, (
        "Verified specs with unchecked tasks require an entry in "
        f"{EXCEPTIONS.relative_to(ROOT)}: {unapproved}"
    )
    assert not stale_exceptions, (
        "Spec task audit exceptions should only cover current historical drift: "
        f"{stale_exceptions}"
    )
