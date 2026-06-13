"""Policy verdict types: the decide-stage interface the Gateway consumes
(FR-110, FR-023).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from loopplane.context import RunContext
from loopplane.events.emitter import EventEmitter
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor


@dataclass(frozen=True)
class PolicyAllow:
    pass


@dataclass(frozen=True)
class PolicyDeny:
    reason: str


PolicyVerdict = PolicyAllow | PolicyDeny

PolicyDecider = Callable[
    [ToolCallRequest, ToolDescriptor, RunContext, EventEmitter],
    Awaitable[PolicyVerdict],
]
