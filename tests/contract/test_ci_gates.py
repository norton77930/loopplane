"""CI quality-gate contract (014): the workflow runs the canonical gates plus an
offline distribution build, and references no secret (FR-030/FR-031; SC-003).
Reads the committed workflow only.
"""

from __future__ import annotations

from tests.release_helpers import REPO_ROOT

CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

CANONICAL_GATES = (
    "ruff format --check",
    "ruff check",
    "mypy",
    "pytest",
    "uv build",
)


def test_ci_runs_the_canonical_gates_and_build() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    missing = [gate for gate in CANONICAL_GATES if gate not in text]
    assert not missing, f"CI workflow is missing gates: {missing}"


def test_ci_references_no_secret() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text, "CI workflow must reference no secret"
