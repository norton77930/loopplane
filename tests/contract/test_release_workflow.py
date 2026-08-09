"""Release workflow contract (082, US2): publishing is tag-only, fail-closed,
and uses least-privilege OIDC without long-lived credentials (FR-004; SC-002).

The workflow is inspected as text so this contract stays offline and adds no YAML
parser dependency. Helpers extract indentation-delimited job blocks before asserting
the security-sensitive conditions.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
_SECRET_REFERENCE = re.compile(r"\bsecrets\s*(?:\.|\[)", re.IGNORECASE)


def _job_block(name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|\Z)",
        TEXT,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing release workflow job: {name}"
    return match.group(0)


def _job_condition(name: str) -> str:
    match = re.search(
        r"^    if: >-\n(?P<condition>(?:      .+\n?)+)",
        _job_block(name),
        re.MULTILINE,
    )
    assert match is not None, f"missing folded if condition on job: {name}"
    return " ".join(line.strip() for line in match.group("condition").splitlines())


def _permissions_from_block(block: str) -> tuple[str, ...] | None:
    scalar = re.search(r"^    permissions:[ \t]+([^\s#]+)", block, re.MULTILINE)
    if scalar is not None:
        return (f"scalar:{scalar.group(1)}",)
    mapping = re.search(
        r"^    permissions:\n(?P<permissions>(?:      .+\n?)+)",
        block,
        re.MULTILINE,
    )
    if mapping is None:
        return None
    return tuple(
        line.strip().split(" #", 1)[0]
        for line in mapping.group("permissions").splitlines()
    )


def _job_permissions(name: str) -> tuple[str, ...] | None:
    return _permissions_from_block(_job_block(name))


def test_release_workflow_has_tag_push_and_manual_dry_run_triggers() -> None:
    assert re.search(r'^  push:\n    tags: \["v\*"\]$', TEXT, re.MULTILINE)
    assert re.search(r"^  workflow_dispatch:$", TEXT, re.MULTILINE)


def test_manual_dispatch_validates_the_requested_tag() -> None:
    checkout_ref = (
        "ref: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.tag || github.ref }}"
    )
    assert checkout_ref in _job_block("validate")


def test_build_uses_the_sha_checked_out_and_validated_by_validate() -> None:
    validate = _job_block("validate")
    build = _job_block("build")

    assert "sha: ${{ steps.commit.outputs.sha }}" in validate
    assert "id: commit" in validate
    assert 'sha="$(git rev-parse HEAD)"' in validate
    assert "ref: ${{ needs.validate.outputs.sha }}" in build
    assert "inputs.tag || github.ref" not in build


def test_publish_is_unreachable_from_dispatch_forks_and_default_dry_run() -> None:
    assert _job_condition("publish") == (
        "github.event_name == 'push' && "
        "startsWith(github.ref, 'refs/tags/v') && "
        "github.repository == 'norton77930/loopplane' && "
        "needs.validate.outputs.dry-run == 'false'"
    )
    assert "needs: [validate, build]" in _job_block("publish")


def test_publish_uses_oidc_and_no_long_lived_secret() -> None:
    publish = _job_block("publish")
    assert "contents: read" in publish
    assert "id-token: write" in publish
    assert "pypa/gh-action-pypi-publish@release/v1" in publish
    assert "skip-existing: true" in publish
    assert _SECRET_REFERENCE.search(TEXT) is None


def test_release_requires_successful_publish_and_is_tag_only() -> None:
    release = _job_block("release")
    assert "needs: [validate, build, publish]" in release
    assert _job_condition("release") == (
        "github.event_name == 'push' && "
        "startsWith(github.ref, 'refs/tags/v') && "
        "github.repository == 'norton77930/loopplane'"
    )
    assert "contents: write" in release


def test_each_job_has_exactly_the_minimum_permissions() -> None:
    assert re.search(r"^permissions:\n  contents: read$", TEXT, re.MULTILINE)
    assert _job_permissions("validate") is None
    assert _job_permissions("build") is None
    assert _job_permissions("publish") == ("contents: read", "id-token: write")
    assert _job_permissions("release") == ("contents: write",)


def test_permission_parser_detects_scalar_write_all_override() -> None:
    block = "  validate:\n    permissions: write-all\n    runs-on: ubuntu-latest\n"
    assert _permissions_from_block(block) == ("scalar:write-all",)


def test_secret_detector_covers_dot_and_bracket_context_forms() -> None:
    assert _SECRET_REFERENCE.search("${{ secrets.PYPI_TOKEN }}")
    assert _SECRET_REFERENCE.search("${{ secrets['PYPI_TOKEN'] }}")
