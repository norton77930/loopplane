"""Runnable example: build a policy sandbox and decide tool calls.

Public-safe and credential-free. A sandbox profile composes permission + path +
capability + budget policies (deny-wins, fail-safe); scripted tool calls are
decided to allow / deny — no tool is ever executed (the gateway owns execution;
Constitution V).

Run::

    python examples/governance_quickstart.py
"""

from __future__ import annotations

import anyio

from loopplane.approval import PermissionRule, PolicyDeny
from loopplane.governance import (
    budget_policy,
    capability_policy,
    path_policy,
    permission_policy,
    sandbox_profile,
)
from loopplane.model import ToolCallRequest, ToolDescriptor


def _call(tool_name: str, **input_kwargs: object) -> ToolCallRequest:
    return ToolCallRequest(call_id="c", tool_name=tool_name, input=dict(input_kwargs))


def _descriptor(name: str, *, read_only: bool = False) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="a demo tool",
        input_schema={"type": "object"},
        concurrency_safe=False,
        read_only=read_only,
        source="demo",
    )


async def run_demo() -> None:
    profile = sandbox_profile(
        permission=permission_policy(
            [PermissionRule(matcher="read_*", effect="allow", scope="project")]
        ),
        path=path_policy("workspace", key="path"),
        capability=capability_policy(require_read_only=True),
        budget=budget_policy(1),
    )

    cases = [
        (
            "read within the sandbox",
            _call("read_file", path="workspace/a.txt"),
            _descriptor("read_file", read_only=True),
        ),
        (
            "a non-permitted, mutating tool",
            _call("write_file", path="workspace/a.txt"),
            _descriptor("write_file", read_only=False),
        ),
        (
            "a path escaping the root",
            _call("read_file", path="../escape"),
            _descriptor("read_file", read_only=True),
        ),
        (
            "a second read over the budget",
            _call("read_file", path="workspace/b.txt"),
            _descriptor("read_file", read_only=True),
        ),
    ]

    print("Sandbox decisions:")
    for label, request, descriptor in cases:
        verdict = await profile(request, descriptor, None, None)
        if isinstance(verdict, PolicyDeny):
            print(f"  DENY  {label} — {verdict.reason}")
        else:
            print(f"  ALLOW {label}")


if __name__ == "__main__":
    anyio.run(run_demo)
