"""078 Desktop Stage-B/C delivery gate contract (T003 RED).

Normative source:
``specs/078-desktop-cowork-parity/contracts/delivery-and-human-gate.md``
and tasks T003–T005 / T090.

T003 writes these tests and observes RED before T004 implements
``scripts/verify-desktop-stage-b.ps1``. Pure policy oracles live in
``tests/helpers/desktop_stage_b_policy.py``; PowerShell entrypoint cases use
``-SelfTest <case>`` and must fail closed without token/header/raw-body leakage.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.desktop_stage_b_policy import (
    C2_SELF_APPROVAL_ENV,
    DESKTOP_PACKAGED_EXTRAS,
    FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY,
    FINAL_TREE_DIFF_ALLOW_DELETE,
    REQUIRED_VERIFIER_TOKEN_ENV,
    TOKEN_ENV_NAMES,
    TreeEntry,
    author_association_allowed,
    c2_self_approval_enabled,
    forbidden_child_token_env_names,
    pairwise_distinct_ids,
    required_locator_keys,
    review_actor_allowed,
    reviewer_login_allowed,
    validate_t002_to_t005_tree_diff,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PS1 = REPO_ROOT / "scripts" / "verify-desktop-stage-b.ps1"

# Cases T004's -SelfTest harness must implement (name → expect success).
SELFTEST_CASES: dict[str, bool] = {
    "modes-declared": True,
    "bootstrap-locators-required": True,
    "final-locators-required": True,
    "delivery-locators-required": True,
    "reject-missing-token": True,
    "reject-empty-token": True,
    "reject-ambient-gh-token-fallback": True,
    "reject-ambient-github-token-fallback": True,
    "reject-bot-reviewer": True,
    "reject-non-collaborator-association": True,
    "reject-expected-approver-mismatch": True,
    "reject-self-approval-when-c2-off": True,
    "allow-self-approval-when-c2-true": True,
    "reject-comment-as-authority": True,
    "reject-pending-review": True,
    "reject-dismissed-review": True,
    "reject-truncated-tree": True,
    "reject-stale-commit-id": True,
    "reject-reused-review-ids": True,
    "tree-diff-allowlist-accepts-t003-t004-only": True,
    "tree-diff-rejects-product-src": True,
    "tree-diff-rejects-workflow-edit": True,
    "tree-diff-rejects-symlink": True,
    "tree-diff-rejects-app-lock-reappearance": True,
    "reject-locator-from-evidence-file": True,
    "reject-token-leak-in-stdout": True,
    "reject-token-leak-in-stderr": True,
    "delivery-child-env-must-scrub-tokens": True,
    "reject-freeze-before-delivery-review": True,
}


# ---------------------------------------------------------------------------
# Pure policy oracle (documents the contract; stable independently of T004)
# ---------------------------------------------------------------------------


def test_policy_mode_locator_keys() -> None:
    assert "bootstrap_review_id" in required_locator_keys("bootstrap")
    assert "final_review_id" in required_locator_keys("final")
    assert "delivery_review_id" in required_locator_keys("delivery")
    assert "bootstrap_review_id" in required_locator_keys("final")
    assert "final_review_id" not in required_locator_keys("bootstrap")


def test_policy_c2_self_approval_exact_true_only() -> None:
    assert c2_self_approval_enabled("true") is True
    assert c2_self_approval_enabled("True") is False
    assert c2_self_approval_enabled("1") is False
    assert c2_self_approval_enabled("") is False
    assert c2_self_approval_enabled(None) is False


def test_policy_reviewer_login_dual_control_and_c2() -> None:
    assert reviewer_login_allowed(
        review_login="alice",
        expected_approver="alice",
        pr_author_login="bob",
        allow_self_approval_raw=None,
    )
    assert not reviewer_login_allowed(
        review_login="bob",
        expected_approver="bob",
        pr_author_login="bob",
        allow_self_approval_raw=None,
    )
    assert reviewer_login_allowed(
        review_login="bob",
        expected_approver="bob",
        pr_author_login="bob",
        allow_self_approval_raw="true",
    )
    assert not reviewer_login_allowed(
        review_login="carol",
        expected_approver="alice",
        pr_author_login="bob",
        allow_self_approval_raw="true",
    )


def test_policy_actor_and_association() -> None:
    assert review_actor_allowed(user_type="User", author_association="COLLABORATOR")
    assert review_actor_allowed(user_type="User", author_association="OWNER")
    assert not review_actor_allowed(user_type="Bot", author_association="COLLABORATOR")
    assert not review_actor_allowed(user_type="User", author_association="CONTRIBUTOR")
    assert not author_association_allowed("NONE")


def test_policy_pairwise_distinct_review_ids() -> None:
    assert pairwise_distinct_ids(1, 2, 3)
    assert not pairwise_distinct_ids(1, 1, 2)
    assert not pairwise_distinct_ids("a", "a")


def test_policy_t002_to_t005_tree_diff_allowlist() -> None:
    t002 = {
        "docs/adr/0015-desktop-cowork-boundary.md": TreeEntry(
            "docs/adr/0015-desktop-cowork-boundary.md", "100644", "blob", "aaa"
        ),
        "apps/web/package-lock.json": TreeEntry(
            "apps/web/package-lock.json", "100644", "blob", "weblock"
        ),
        "apps/desktop/package-lock.json": TreeEntry(
            "apps/desktop/package-lock.json", "100644", "blob", "desklock"
        ),
        "src/loopplane/host/host.py": TreeEntry(
            "src/loopplane/host/host.py", "100644", "blob", "host1"
        ),
    }
    t005_ok = {
        "docs/adr/0015-desktop-cowork-boundary.md": TreeEntry(
            "docs/adr/0015-desktop-cowork-boundary.md", "100644", "blob", "aaa"
        ),
        "src/loopplane/host/host.py": TreeEntry(
            "src/loopplane/host/host.py", "100644", "blob", "host1"
        ),
        "tests/contract/test_desktop_delivery_gate.py": TreeEntry(
            "tests/contract/test_desktop_delivery_gate.py", "100644", "blob", "t003"
        ),
        "scripts/verify-desktop-stage-b.ps1": TreeEntry(
            "scripts/verify-desktop-stage-b.ps1", "100644", "blob", "t004"
        ),
        "package.json": TreeEntry("package.json", "100644", "blob", "rootpkg"),
        "package-lock.json": TreeEntry(
            "package-lock.json", "100644", "blob", "rootlock"
        ),
        "apps/web/package.json": TreeEntry(
            "apps/web/package.json", "100644", "blob", "webpkg"
        ),
        "apps/desktop/package.json": TreeEntry(
            "apps/desktop/package.json", "100644", "blob", "despkg"
        ),
        "packages/cowork-presentation/package.json": TreeEntry(
            "packages/cowork-presentation/package.json", "100644", "blob", "shared"
        ),
        "specs/078-desktop-cowork-parity/implementation-evidence.md": TreeEntry(
            "specs/078-desktop-cowork-parity/implementation-evidence.md",
            "100644",
            "blob",
            "ev",
        ),
    }
    assert validate_t002_to_t005_tree_diff(before=t002, after=t005_ok) == []

    t005_bad_src = dict(t005_ok)
    t005_bad_src["src/loopplane/host/host.py"] = TreeEntry(
        "src/loopplane/host/host.py", "100644", "blob", "host2"
    )
    viol = validate_t002_to_t005_tree_diff(before=t002, after=t005_bad_src)
    assert any(v.path.endswith("host.py") for v in viol)

    t005_bad_add = dict(t005_ok)
    t005_bad_add["src/loopplane/host/audit.py"] = TreeEntry(
        "src/loopplane/host/audit.py", "100644", "blob", "new"
    )
    viol2 = validate_t002_to_t005_tree_diff(before=t002, after=t005_bad_add)
    assert any(v.reason == "disallowed_addition" for v in viol2)

    t005_symlink = dict(t005_ok)
    t005_symlink["scripts/verify-desktop-stage-b.ps1"] = TreeEntry(
        "scripts/verify-desktop-stage-b.ps1", "120000", "blob", "link"
    )
    viol3 = validate_t002_to_t005_tree_diff(before=t002, after=t005_symlink)
    assert viol3


def test_policy_allowlists_and_extras_are_frozen() -> None:
    assert "scripts/verify-desktop-stage-b.ps1" in FINAL_TREE_DIFF_ALLOW_ADD_OR_MODIFY
    assert "apps/web/package-lock.json" in FINAL_TREE_DIFF_ALLOW_DELETE
    assert DESKTOP_PACKAGED_EXTRAS == {
        "anthropic",
        "gemini",
        "mcp",
        "net",
        "oauth",
        "openai",
    }
    assert REQUIRED_VERIFIER_TOKEN_ENV == "LOOPPLANE_STAGE_B_GITHUB_TOKEN"
    assert set(forbidden_child_token_env_names()) == set(TOKEN_ENV_NAMES)
    assert C2_SELF_APPROVAL_ENV == "LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL"


# ---------------------------------------------------------------------------
# Verifier entrypoint (RED until T004 materializes the script + -SelfTest)
# ---------------------------------------------------------------------------


def test_verifier_script_exists_at_canonical_path() -> None:
    """T004 must create scripts/verify-desktop-stage-b.ps1 — RED until then."""

    assert VERIFIER_PS1.is_file(), (
        "missing scripts/verify-desktop-stage-b.ps1 "
        "(T004 implements bootstrap/final/delivery modes here)"
    )


def _run_selftest(
    case: str, *, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    if not VERIFIER_PS1.is_file():
        pytest.fail(
            f"T004 missing {VERIFIER_PS1.as_posix()}; "
            f"cannot run SelfTest case {case!r}"
        )
    env = os.environ.copy()
    # Scrub ambient GitHub tokens so cases control the credential seam.
    for name in TOKEN_ENV_NAMES:
        env.pop(name, None)
    if extra_env:
        env.update(extra_env)
    # Prefer pwsh, fall back to Windows PowerShell.
    shell = "pwsh" if sys.platform != "win32" else "powershell"
    cmd = [
        shell,
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(VERIFIER_PS1),
        "-SelfTest",
        case,
    ]
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def _assert_no_secret_leak(result: subprocess.CompletedProcess[str]) -> None:
    blob = (result.stdout or "") + (result.stderr or "")
    # Never echo a bearer token or raw authorization header.
    assert not re.search(r"(?i)authorization\s*:\s*bearer\s+\S+", blob)
    assert "ghs_" not in blob
    assert "github_pat_" not in blob
    # Synthetic tokens used only inside SelfTest must not be echoed either.
    assert "TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK" not in blob


@pytest.mark.parametrize("case,expect_ok", sorted(SELFTEST_CASES.items()))
def test_verifier_selftest_case(case: str, expect_ok: bool) -> None:
    """Each named SelfTest case must pass (exit 0) under T004 — RED while missing."""

    result = _run_selftest(case)
    _assert_no_secret_leak(result)
    if expect_ok:
        assert result.returncode == 0, (
            f"SelfTest {case!r} expected success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    else:
        assert result.returncode != 0


def test_verifier_live_invocation_rejects_missing_token() -> None:
    """Live (non-SelfTest) entry without LOOPPLANE_STAGE_B_GITHUB_TOKEN fails closed."""

    if not VERIFIER_PS1.is_file():
        pytest.fail(f"T004 missing {VERIFIER_PS1.as_posix()}")
    env = os.environ.copy()
    for name in TOKEN_ENV_NAMES:
        env.pop(name, None)
    shell = "pwsh" if sys.platform != "win32" else "powershell"
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(VERIFIER_PS1),
            "-Mode",
            "bootstrap",
            "-Owner",
            "norton77930",
            "-Repository",
            "loopplane",
            "-PullNumber",
            "3",
            "-ExpectedApprover",
            "norton777930",
            "-BootstrapReviewId",
            "4864730949",
            "-BootstrapCommitSha",
            "5319634a7e5c77b21ffa5355595fae18f9d82083",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    _assert_no_secret_leak(result)
    assert result.returncode != 0


def test_verifier_does_not_accept_gh_token_as_credential_seam() -> None:
    """Only LOOPPLANE_STAGE_B_GITHUB_TOKEN is accepted — GH_TOKEN alone is not."""

    if not VERIFIER_PS1.is_file():
        pytest.fail(f"T004 missing {VERIFIER_PS1.as_posix()}")
    result = _run_selftest(
        "reject-ambient-gh-token-fallback",
        extra_env={"GH_TOKEN": "TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK"},
    )
    _assert_no_secret_leak(result)
    assert result.returncode == 0


def test_t006_plus_must_not_mutate_accepted_manifest_paths_in_tasks() -> None:
    """Guardrail: post-T005 tasks must not rewrite accepted package manifests/locks.

    T003 documents the immutability rule; full enforcement is T004/T005 + later
    static review. This test fails if tasks.md lists manifest edits after T005
    outside an explicit return-to-T004 note.
    """

    tasks = (REPO_ROOT / "specs/078-desktop-cowork-parity/tasks.md").read_text(
        encoding="utf-8"
    )
    # Split at T006 so only later product tasks are scanned for forbidden rewrite
    # of the accepted root lock without returning to T004/T005.
    marker = "- [ ] T006"
    if marker not in tasks:
        marker = "- [x] T006"
    assert "T006" in tasks
    after = tasks.split("T006", 1)[1]
    forbidden = [
        "regenerate package-lock.json",
        "edit accepted package-lock.json",
        "mutate the sole root lock",
        "rewrite apps/web/package.json dependencies",
    ]
    hits = [f for f in forbidden if f in after.lower()]
    assert not hits, f"T006+ tasks appear to mutate accepted locks: {hits}"
