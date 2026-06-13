"""Public-safety scan over committed files (SC-006, constitution VII).

Permanent contract test: no committed file may contain secret-looking values,
private network addresses, or absolute local user paths. Additional patterns
may be supplied locally through a gitignored ``sensitive-scan.txt`` at the
repository root (one regular expression per line; blank lines and ``#``
comments are ignored).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PATTERN_FILE = REPO_ROOT / "sensitive-scan.txt"

# Built-in patterns are assembled from fragments so this file never matches
# its own source.
_PRIVATE_KEY_BLOCK = "-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"
_AWS_ACCESS_KEY_ID = "AKIA" + r"[0-9A-Z]{16}"
_GITHUB_TOKEN = "ghp" + r"_[A-Za-z0-9]{36}"
_ASSIGNED_SECRET = (
    r"(?i)\b(api[_-]?key|secret|tok"
    + r"en|passw"
    + r"ord)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"
)
_PRIVATE_IPV4 = (
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
_WINDOWS_USER_PATH = r"[A-Za-z]:\\+Use" + r"rs\\+\w+"
_POSIX_HOME_PATH = r"(?:/ho" + r"me|/Use" + r"rs)/\w+"

BUILTIN_PATTERNS: dict[str, str] = {
    "private key block": _PRIVATE_KEY_BLOCK,
    "AWS access key id": _AWS_ACCESS_KEY_ID,
    "GitHub personal access token": _GITHUB_TOKEN,
    "assigned secret value": _ASSIGNED_SECRET,
    "private network address": _PRIVATE_IPV4,
    "absolute Windows user path": _WINDOWS_USER_PATH,
    "absolute POSIX home path": _POSIX_HOME_PATH,
}


def _committed_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [REPO_ROOT / name for name in output.decode("utf-8").split("\0") if name]


def _read_text(path: Path) -> str | None:
    """Return file text, or None for binary or unreadable files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _load_local_patterns() -> dict[str, str]:
    if not LOCAL_PATTERN_FILE.is_file():
        return {}
    patterns: dict[str, str] = {}
    lines = LOCAL_PATTERN_FILE.read_text("utf-8").splitlines()
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns[f"local pattern (line {index})"] = stripped
    return patterns


def test_committed_files_are_public_safe() -> None:
    patterns = {**BUILTIN_PATTERNS, **_load_local_patterns()}
    compiled = {label: re.compile(pattern) for label, pattern in patterns.items()}

    violations: list[str] = []
    for path in _committed_files():
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Public-safety scan found:\n" + "\n".join(violations)


# Phase-2 host-integration files are covered explicitly so they are scanned even
# before they are committed (T023; SC-006, FR-052).
PHASE2_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "host",
    REPO_ROOT / "examples" / "host_quickstart.py",
    REPO_ROOT / "docs" / "embedding-host.md",
]


def test_phase2_host_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE2_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-2 host files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-2 public-safety scan found:\n" + "\n".join(violations)


# Phase-3 loop-engineering files are covered explicitly so they are scanned even
# before they are committed (T042; SC-010, NFR-004).
PHASE3_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "engineering",
    REPO_ROOT / "examples" / "loop_quickstart.py",
    REPO_ROOT / "docs" / "loop-engineering.md",
    REPO_ROOT / "specs" / "003-loopplane-loop-engineering-layer",
]


def test_phase3_engineering_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE3_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
            targets.extend(sorted(target.rglob("*.md")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-3 loop-engineering files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-3 public-safety scan found:\n" + "\n".join(violations)


# Phase-4 scheduler files are covered explicitly so they are scanned even before
# they are committed (T031; SC-010, NFR-004).
PHASE4_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "scheduling",
    REPO_ROOT / "examples" / "scheduler_quickstart.py",
    REPO_ROOT / "docs" / "scheduling.md",
    REPO_ROOT / "specs" / "004-loopplane-scheduler-trigger-engine",
]


def test_phase4_scheduling_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE4_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
            targets.extend(sorted(target.rglob("*.md")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-4 scheduler files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-4 public-safety scan found:\n" + "\n".join(violations)


# Phase-5 pack files are covered explicitly so they are scanned even before they
# are committed (T028; SC-010, NFR-004).
PHASE5_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "packs",
    REPO_ROOT / "examples" / "packs_quickstart.py",
    REPO_ROOT / "docs" / "packs.md",
    REPO_ROOT / "specs" / "005-loopplane-validator-evaluator-packs",
]


def test_phase5_pack_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE5_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
            targets.extend(sorted(target.rglob("*.md")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-5 pack files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-5 public-safety scan found:\n" + "\n".join(violations)


# Phase-6 human-review files are covered explicitly so they are scanned even
# before they are committed (T028; SC-010, NFR-004).
PHASE6_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "review",
    REPO_ROOT / "examples" / "review_quickstart.py",
    REPO_ROOT / "docs" / "human-review.md",
    REPO_ROOT / "specs" / "006-loopplane-human-review-workflows",
]


def test_phase6_review_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE6_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
            targets.extend(sorted(target.rglob("*.md")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-6 review files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-6 public-safety scan found:\n" + "\n".join(violations)


# Phase-7 recall files are covered explicitly so they are scanned even before they
# are committed (T025; SC-006, NFR-002).
PHASE7_TARGETS = [
    REPO_ROOT / "src" / "loopplane" / "recall",
    REPO_ROOT / "examples" / "recall_quickstart.py",
    REPO_ROOT / "docs" / "memory-recall.md",
    REPO_ROOT / "specs" / "007-loopplane-memory-recall-knowledge",
]


def test_phase7_recall_files_are_public_safe() -> None:
    compiled = {
        label: re.compile(pattern) for label, pattern in BUILTIN_PATTERNS.items()
    }

    targets: list[Path] = []
    for target in PHASE7_TARGETS:
        if target.is_dir():
            targets.extend(sorted(target.rglob("*.py")))
            targets.extend(sorted(target.rglob("*.md")))
        elif target.is_file():
            targets.append(target)
    assert targets, "expected Phase-7 recall files to scan"

    violations: list[str] = []
    for path in targets:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, regex in compiled.items():
                if regex.search(line):
                    violations.append(f"{relative}:{lineno}: {label}")

    assert not violations, "Phase-7 public-safety scan found:\n" + "\n".join(violations)
