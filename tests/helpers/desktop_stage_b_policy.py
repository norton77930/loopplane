"""Pure policy oracle for 078 Stage-B / Stage-C delivery gate (T003).

These functions encode the normative allowlists and mode rules from
``specs/078-desktop-cowork-parity/contracts/delivery-and-human-gate.md``.
T004's ``scripts/verify-desktop-stage-b.ps1`` must implement equivalent
behaviour; contract tests load this module as the oracle and exercise the
PowerShell entrypoint via ``-SelfTest``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Mode = Literal["bootstrap", "final", "delivery"]

ALLOWED_AUTHOR_ASSOCIATIONS: Final[frozenset[str]] = frozenset(
    {"OWNER", "MEMBER", "COLLABORATOR"}
)

# Exact T002→T005 full-tree allowlist (regular 100644 blobs only).
FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY: Final[frozenset[str]] = frozenset(
    {
        "tests/contract/test_desktop_delivery_gate.py",
        "scripts/verify-desktop-stage-b.ps1",
        "package.json",
        "package-lock.json",
        "apps/web/package.json",
        "apps/desktop/package.json",
        "packages/cowork-presentation/package.json",
        "specs/078-desktop-cowork-parity/implementation-evidence.md",
    }
)

FINAL_TREE_DIFF_ALLOW_DELETE: Final[frozenset[str]] = frozenset(
    {
        "apps/web/package-lock.json",
        "apps/desktop/package-lock.json",
    }
)

TOKEN_ENV_NAMES: Final[tuple[str, ...]] = (
    "LOOPPLANE_STAGE_B_GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)

REQUIRED_VERIFIER_TOKEN_ENV: Final[str] = "LOOPPLANE_STAGE_B_GITHUB_TOKEN"
C2_SELF_APPROVAL_ENV: Final[str] = "LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL"

DESKTOP_PACKAGED_EXTRAS: Final[frozenset[str]] = frozenset(
    {"anthropic", "gemini", "mcp", "net", "oauth", "openai"}
)


@dataclass(frozen=True, slots=True)
class TreeEntry:
    """One recursive-tree inventory row (path, git mode, type, blob/tree sha)."""

    path: str
    mode: str
    entry_type: str  # "blob" | "tree" | "commit"
    sha: str


@dataclass(frozen=True, slots=True)
class TreeDiffViolation:
    path: str
    reason: str


def required_locator_keys(mode: Mode) -> tuple[str, ...]:
    """Immutable invocation keys required for each verifier mode."""

    shared = (
        "owner",
        "repository",
        "pull_number",
        "expected_approver",
    )
    if mode == "bootstrap":
        return shared + ("bootstrap_review_id", "bootstrap_commit_sha")
    if mode == "final":
        return shared + (
            "bootstrap_review_id",
            "bootstrap_commit_sha",
            "final_review_id",
            "final_commit_sha",
        )
    return shared + (
        "bootstrap_review_id",
        "bootstrap_commit_sha",
        "final_review_id",
        "final_commit_sha",
        "delivery_review_id",
        "delivery_commit_sha",
    )


def c2_self_approval_enabled(raw: str | None) -> bool:
    """Solo self-approval only when the repository variable is exactly ``true``."""

    return raw == "true"


def reviewer_login_allowed(
    *,
    review_login: str,
    expected_approver: str,
    pr_author_login: str,
    allow_self_approval_raw: str | None,
) -> bool:
    """Expected-approver equality plus C2 dual-control / solo rule."""

    if review_login != expected_approver:
        return False
    if review_login.casefold() == pr_author_login.casefold():
        return c2_self_approval_enabled(allow_self_approval_raw)
    return True


def author_association_allowed(association: str) -> bool:
    return association in ALLOWED_AUTHOR_ASSOCIATIONS


def review_actor_allowed(*, user_type: str, author_association: str) -> bool:
    return user_type == "User" and author_association_allowed(author_association)


def pairwise_distinct_ids(*ids: str | int) -> bool:
    normalized = [str(i) for i in ids]
    return len(normalized) == len(set(normalized)) and all(normalized)


def validate_t002_to_t005_tree_diff(
    *,
    before: dict[str, TreeEntry],
    after: dict[str, TreeEntry],
) -> list[TreeDiffViolation]:
    """Return violations for the exact T002→T005 full-tree allowlist.

    Permitted:
    - add/modify only paths in ``FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY`` as mode
      ``100644`` blobs (additions) or same-mode ``100644`` blob modifications;
    - delete only the two app-local package-locks.

    Every other path/type/mode/blob change is a violation.
    """

    violations: list[TreeDiffViolation] = []
    before_paths = set(before)
    after_paths = set(after)

    for path in sorted(after_paths - before_paths):
        entry = after[path]
        if path not in FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY:
            violations.append(TreeDiffViolation(path, "disallowed_addition"))
            continue
        if entry.entry_type != "blob" or entry.mode != "100644":
            violations.append(TreeDiffViolation(path, "addition_must_be_100644_blob"))

    for path in sorted(before_paths - after_paths):
        if path not in FINAL_TREE_DIFF_ALLOW_DELETE:
            violations.append(TreeDiffViolation(path, "disallowed_deletion"))

    for path in sorted(before_paths & after_paths):
        left, right = before[path], after[path]
        if (
            left.mode == right.mode
            and left.entry_type == right.entry_type
            and left.sha == right.sha
        ):
            continue
        if path not in FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY:
            violations.append(TreeDiffViolation(path, "disallowed_modification"))
            continue
        if left.entry_type != "blob" or right.entry_type != "blob":
            violations.append(TreeDiffViolation(path, "modification_must_remain_blob"))
            continue
        if left.mode != "100644" or right.mode != "100644":
            violations.append(TreeDiffViolation(path, "modification_must_keep_100644"))
            continue
        if left.mode != right.mode:
            violations.append(TreeDiffViolation(path, "mode_change_forbidden"))

    return violations


def forbidden_child_token_env_names() -> tuple[str, ...]:
    """Token names that package/freeze/smoke descendants must not inherit."""

    return TOKEN_ENV_NAMES
