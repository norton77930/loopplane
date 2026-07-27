"""Safe, ephemeral agent-control projection for the Web host (spec 077).

This module owns only browser-safe projection values and host-side validation.  It
never owns Gateway authorization, persistence, or transport behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from loopplane.budget import BudgetPostureSnapshot
from loopplane.governance.modes import PERMISSION_MODES
from loopplane.host.config import RuntimeConfig

_PUBLIC_MODE_SUMMARIES: dict[str, str] = {
    "acceptEdits": "permission.mode.accept_edits",
    "dontAsk": "permission.mode.dont_ask",
    "plan": "permission.mode.plan",
}
_BYPASSING_MODES = frozenset({"bypassPermissions"})


@dataclass(frozen=True)
class PermissionModeOption:
    """One host-approved browser choice; its summary is a client i18n key."""

    id: str
    kind: Literal["standard", "plan"]
    summary: str


@dataclass(frozen=True)
class AcceptedRunPosture:
    """Ephemeral, display-only metadata for a host-accepted run."""

    mode: str
    state: Literal["active", "settled"]
    plan_active: bool


@dataclass(frozen=True)
class PermissionPosture:
    default_mode: str | None
    selectable_modes: tuple[PermissionModeOption, ...]
    selection_scope: Literal["run"]
    rules_configured: bool
    rule_default: Literal["allow", "ask", "deny"] | None
    rule_decisions: tuple[Literal["allow", "ask", "deny"], ...]
    plan_entry_available: bool
    plan_exit_requires_approval: bool
    active_run: AcceptedRunPosture | None
    last_accepted_run: AcceptedRunPosture | None


@dataclass(frozen=True)
class BudgetGuardPosture:
    """Public-safe execution-cost posture containing no caps, rates, or identities."""

    tracking: Literal["available", "unavailable", "unknown"] = "unknown"
    pricing: Literal["priced", "partially_unpriced", "unpriced", "unknown"] = "unknown"
    message_guard: Literal["enabled", "disabled", "unknown"] = "unknown"
    session_guard: Literal["within", "near", "exceeded", "disabled", "unknown"] = (
        "unknown"
    )
    monthly_guard: Literal["within", "near", "exceeded", "disabled", "unknown"] = (
        "unknown"
    )
    pre_turn_guard: Literal["enabled", "disabled", "unknown"] = "unknown"


@dataclass(frozen=True)
class AgentControlProjection:
    session_id: str
    permission: PermissionPosture
    budget: BudgetGuardPosture
    actions: tuple[str, ...]


def selectable_browser_modes(config: RuntimeConfig) -> tuple[PermissionModeOption, ...]:
    """Return host-approved modes or fail closed for invalid configuration.

    ``bypassPermissions`` is never a browser capability, even when an embedding host
    can configure it for a non-browser use case.  A duplicate/unknown mode makes the
    complete browser selection read-only rather than guessing an effective policy.
    """

    identifiers = config.browser_permission_modes
    if (
        len(set(identifiers)) != len(identifiers)
        or any(mode not in PERMISSION_MODES for mode in identifiers)
        or any(mode in _BYPASSING_MODES for mode in identifiers)
    ):
        return ()
    return tuple(
        PermissionModeOption(
            id=mode,
            kind="plan" if mode == "plan" else "standard",
            summary=_PUBLIC_MODE_SUMMARIES[mode],
        )
        for mode in identifiers
        if mode in _PUBLIC_MODE_SUMMARIES
    )


def validate_browser_permission_mode(
    config: RuntimeConfig, mode: str | None
) -> str | None:
    """Validate a submitted one-run selection without echoing rejected input.

    A ``ValueError`` intentionally carries a fixed public-safe message.  WebAPI
    converts it to a fixed 400 before model or Gateway work begins.
    """

    if mode is None:
        return None
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("permission mode unavailable")
    allowed = {option.id for option in selectable_browser_modes(config)}
    if mode not in allowed:
        raise ValueError("permission mode unavailable")
    return mode


def _safe_default_mode(config: RuntimeConfig) -> str | None:
    """Return a public default only when it is never an approval bypass."""

    mode = config.permission_mode
    if mode in _BYPASSING_MODES:
        return None
    return mode if mode in _PUBLIC_MODE_SUMMARIES else None


def _rule_decisions(
    config: RuntimeConfig,
) -> tuple[Literal["allow", "ask", "deny"], ...]:
    rules = config.permission_rules
    if rules is None:
        return ()
    ordered: list[Literal["allow", "ask", "deny"]] = []
    for decision in (*[rule.decision for rule in rules.rules], rules.default):
        if decision not in ordered:
            ordered.append(decision)
    return tuple(ordered)


def build_agent_control_projection(
    config: RuntimeConfig,
    *,
    session_id: str,
    active_run: AcceptedRunPosture | None = None,
    last_accepted_run: AcceptedRunPosture | None = None,
    budget: BudgetPostureSnapshot | None = None,
    read_upload_available: bool = False,
) -> AgentControlProjection:
    """Build the safe owner-scoped read model from host-owned inputs only."""

    modes = selectable_browser_modes(config)
    rules = config.permission_rules
    actions: list[str] = []
    if modes:
        actions.append("select_permission_mode")
    if read_upload_available:
        actions.append("attach_non_image_upload")
    budget_source = budget or BudgetPostureSnapshot()
    return AgentControlProjection(
        session_id=session_id,
        permission=PermissionPosture(
            default_mode=_safe_default_mode(config),
            selectable_modes=modes,
            selection_scope="run",
            rules_configured=rules is not None,
            rule_default=rules.default if rules is not None else None,
            rule_decisions=_rule_decisions(config),
            plan_entry_available=any(option.kind == "plan" for option in modes),
            plan_exit_requires_approval=any(option.kind == "plan" for option in modes),
            active_run=active_run,
            last_accepted_run=last_accepted_run,
        ),
        budget=BudgetGuardPosture(
            tracking=budget_source.tracking,
            pricing=budget_source.pricing,
            message_guard=budget_source.message_guard,
            session_guard=budget_source.session_guard,
            monthly_guard=budget_source.monthly_guard,
            pre_turn_guard=budget_source.pre_turn_guard,
        ),
        actions=tuple(actions),
    )
