"""Boundary and cross-cutting contract tests for the governance layer
(009; NFR-001, NFR-003, NFR-006, SC-002/005/009).

The layer composes only the public Phase-1 policy contracts, never imports the
Tool Gateway implementation or the Human-Approval interaction symbols, never
executes a tool, and reuses the Phase-1 rule engine.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.approval import PermissionRule, PolicyAllow, PolicyDeny, resolve_rules
from loopplane.governance import path_policy, permission_policy
from tests.governance_helpers import call, decide, descriptor

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DIR = REPO_ROOT / "src" / "loopplane" / "governance"

ALLOWED_PREFIXES = (
    "loopplane.approval",
    "loopplane.model",
    "loopplane.context",
    "loopplane.events",
    "loopplane.governance",
)
PROHIBITED_IMPORT_NAMES = (
    "InteractionBroker",
    "ApprovalResolution",
    "ResolutionSource",
    "HumanApproval",
    "ToolGateway",
    "ToolHandler",
)


def _modules() -> list[Path]:
    return sorted(GOVERNANCE_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_governance_imports_only_public_policy_contracts() -> None:
    violations: list[str] = []
    for path in _modules():
        for node in ast.walk(_parsed(path)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith("loopplane") and not any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in ALLOWED_PREFIXES
                ):
                    violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_governance_imports_no_gateway_or_interaction_symbol() -> None:
    violations: list[str] = []
    for path in _modules():
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in PROHIBITED_IMPORT_NAMES:
                        violations.append(f"{path.name}: imports {alias.name}")
    assert not violations, "Prohibited symbols:\n" + "\n".join(violations)


def test_governance_never_executes_a_tool() -> None:
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        if ".invoke(" in text or ".run(" in text:
            violations.append(f"{path.name}: references an execution surface")
    assert not violations, "Executes a tool:\n" + "\n".join(violations)


@pytest.mark.anyio
async def test_permission_verdicts_match_resolve_rules() -> None:
    rules = [
        PermissionRule(matcher="read*", effect="allow", scope="project"),
        PermissionRule(matcher="read_secret", effect="deny", scope="session-local"),
    ]
    policy = permission_policy(rules)
    for name in ("read_file", "read_secret", "write"):
        verdict = await decide(policy, call(name), descriptor())
        if resolve_rules(rules, name) == "allow":
            assert isinstance(verdict, PolicyAllow)
        else:
            assert isinstance(verdict, PolicyDeny)


@pytest.mark.anyio
async def test_decisions_are_deterministic() -> None:
    policy = path_policy("sandbox")
    contained = call("read", path="sandbox/x")
    first = await decide(policy, contained, descriptor())
    second = await decide(policy, contained, descriptor())
    assert type(first) is type(second)
