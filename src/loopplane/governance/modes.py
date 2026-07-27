"""Named convenience permission modes (spec 066; gap G10).

Four named presets built from the EXISTING 039 permission rule DSL — a host selects
one via ``RuntimeConfig.permission_mode`` instead of hand-authoring a
:class:`~loopplane.governance.rule_dsl.PermissionRuleSet`:

- ``acceptEdits`` — auto-allow the file-edit tools (write/edit/notebook/undo);
  everything else follows ``default="ask"``.
- ``bypassPermissions`` — allow everything (``default="allow"``, no rules): the
  clearly-named escape hatch (it relaxes only the permission-rule posture; tools
  still run through the Tool Gateway, and any network/approval gate still applies).
- ``dontAsk`` — take the host's explicit rules (or an empty allow-all set) and
  rewrite every ``ask`` decision to ``allow`` (a pure transform): never prompts,
  keeps ``deny``.
- ``plan`` — the existing 038 plan mode (the builder returns ``None``; the caller
  sets ``plan_mode``).

A mode produces a plain ``PermissionRuleSet`` (data) fed through the SAME
``rule_dsl_policy`` decider at the SAME decide stage — no new decider kind, no new
gateway stage, no event/schema change. Public-safe (plain tool-name rules).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.governance.base import allow, deny
from loopplane.governance.rule_dsl import (
    PermissionRuleSet,
    PermissionRuleSpec,
    rule_dsl_policy,
)

if TYPE_CHECKING:
    from loopplane.approval import PolicyDecider, PolicyVerdict
    from loopplane.context import RunContext
    from loopplane.events.emitter import EventEmitter
    from loopplane.model import ToolCallRequest, ToolDescriptor

__all__ = [
    "PERMISSION_MODES",
    "per_run_permission_mode_policy",
    "permission_mode_ruleset",
]

PERMISSION_MODES: tuple[str, ...] = (
    "acceptEdits",
    "bypassPermissions",
    "dontAsk",
    "plan",
)

# The mutating file tools auto-allowed by ``acceptEdits`` (the 033/046/054 baseline
# file-write tools; read/search tools are not edits).
_EDIT_TOOLS: tuple[str, ...] = ("write_file", "edit_file", "notebook_edit", "undo_file")


def permission_mode_ruleset(
    mode: str, explicit_rules: PermissionRuleSet | None
) -> PermissionRuleSet | None:
    """The effective ``PermissionRuleSet`` for a named mode (or ``None`` for ``plan``,
    where the caller sets ``plan_mode`` instead). Reuses the 039 DSL; raises
    :class:`ValueError` for an unknown mode (config validation surfaces it)."""

    if mode == "plan":
        return None
    if mode == "acceptEdits":
        return PermissionRuleSet(
            rules=tuple(
                PermissionRuleSpec(tool=tool, decision="allow") for tool in _EDIT_TOOLS
            ),
            default="ask",
        )
    if mode == "bypassPermissions":
        return PermissionRuleSet(rules=(), default="allow")
    if mode == "dontAsk":
        base = explicit_rules if explicit_rules is not None else PermissionRuleSet()
        rewritten = tuple(
            rule
            if rule.decision != "ask"
            else rule.model_copy(update={"decision": "allow"})
            for rule in base.rules
        )
        default = "allow" if base.default == "ask" else base.default
        return PermissionRuleSet(rules=rewritten, default=default)
    raise ValueError(f"unknown permission mode: {mode!r}")


def per_run_permission_mode_policy(allowed_modes: tuple[str, ...]) -> PolicyDecider:
    """Return the existing-decider overlay for a host-approved run selection.

    The browser input is rechecked defensively at the Gateway decide seam.  This
    policy does not replace any configured rule/approval/network/plan policy: assembly
    composes it through the existing deny-wins combinator, so an explicit or safety
    denial still wins.  ``bypassPermissions`` is deliberately invalid even if an
    embedding host incorrectly supplies it here.
    """

    allowed = frozenset(allowed_modes) - {"bypassPermissions"}
    policies = {
        mode: rule_dsl_policy(rules)
        for mode in allowed
        if mode != "plan"
        for rules in (permission_mode_ruleset(mode, None),)
        if rules is not None
    }

    async def decider(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        mode = context.permission_mode
        if mode is None:
            return allow()
        if mode not in allowed or mode not in PERMISSION_MODES:
            return deny("permission mode unavailable")
        if mode == "plan":
            return allow()
        policy = policies.get(mode)
        if policy is None:
            return deny("permission mode unavailable")
        return await policy(call, descriptor, context, emitter)

    return decider
