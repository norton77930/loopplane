"""LoopPlane lifecycle hooks (feature 015-loopplane-hook-system).

An in-process extensibility layer: a :class:`HookRegistry` of caller-supplied
callbacks invoked at eleven well-defined :class:`LifecyclePoint` moments. Nine
points are observational; the two gating points (``before_tool_use``,
``user_prompt_submit``) let a hook return a decision that allows, denies/blocks,
or modifies/annotates. Hooks are additive and inert by default — the runtime
registers none, and with no registry configured every component runs its existing
path unchanged. Tool-boundary hooks fire **inside** the Tool Gateway (Constitution
V); the hook system stays distinct from the Runtime Event Bus, and a hook failure
surfaces only through the existing metadata-only ``diagnostic`` event (VI).
"""

from __future__ import annotations

from loopplane.hooks.decisions import (
    PromptAllow,
    PromptAnnotate,
    PromptBlock,
    PromptDecision,
    ToolGateAllow,
    ToolGateDecision,
    ToolGateDeny,
    ToolGateModify,
)
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.hooks.points import (
    AfterToolFailurePayload,
    AfterToolUsePayload,
    BeforeToolUsePayload,
    FileChangedPayload,
    LifecyclePoint,
    ModelStopPayload,
    ProcessSetupPayload,
    SessionEndPayload,
    SessionStartPayload,
    SubagentStartPayload,
    SubagentStopPayload,
    UserPromptSubmitPayload,
    is_gating,
)
from loopplane.hooks.registry import HookCallback, HookRegistry

__all__ = [
    "AfterToolFailurePayload",
    "AfterToolUsePayload",
    "BeforeToolUsePayload",
    "FileChangedPayload",
    "HookCallback",
    "HookDispatcher",
    "HookRegistry",
    "LifecyclePoint",
    "ModelStopPayload",
    "ProcessSetupPayload",
    "PromptAllow",
    "PromptAnnotate",
    "PromptBlock",
    "PromptDecision",
    "SessionEndPayload",
    "SessionStartPayload",
    "SubagentStartPayload",
    "SubagentStopPayload",
    "ToolGateAllow",
    "ToolGateDecision",
    "ToolGateDeny",
    "ToolGateModify",
    "UserPromptSubmitPayload",
    "is_gating",
]
