"""Runnable example: gate a loop on a human review workflow.

Public-safe and credential-free. A scripted loop returns ``needs_human_review``;
a review gate built from an (auto-approving) reviewer resolves it through the
Phase-3 ``run_loop``, printing the review event stream.

Run::

    python examples/review_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopOutcome,
    LoopState,
    ManualTrigger,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    run_loop,
    stop_on_pass,
)
from loopplane.host import LoopPlaneHost, RunOutcome, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.review import (
    ReviewContext,
    ReviewDecision,
    ReviewEvent,
    ReviewRequest,
    build_review_resolver,
)


def _needs_review(outcome: RunOutcome, state: LoopState) -> ValidationResult:
    return ValidationResult(
        status="needs_human_review", reason="please review the draft"
    )


def _reviewer(request: ReviewRequest, context: ReviewContext) -> ReviewDecision:
    # A scripted demo reviewer that approves; a real host plugs a human here.
    return ReviewDecision(
        outcome="approve", reason="approved by the demo reviewer", reviewer="demo"
    )


async def run_demo(working_scope: Path | None = None) -> LoopOutcome:
    scope = working_scope or Path.cwd()

    def build_host() -> LoopPlaneHost:
        model = ScriptedModel(
            script=[ScriptedTurn(increments=[TextIncrement(text="draft report")])],
            context_capacity=100_000,
        )
        return LoopPlaneHost(RuntimeConfig(model=model), working_scope=scope)

    events: list[ReviewEvent] = []

    async def on_event(event: ReviewEvent) -> None:
        events.append(event)

    definition = LoopDefinition(
        loop_id="review-demo",
        trigger=ManualTrigger(),
        input_source=StaticInput("write a report"),
        host_profile=HostRuntimeProfile(selector=build_host),
        validation_policy=ValidationPolicy(validator=_needs_review),
        stop_condition=stop_on_pass(),
    )
    gate = build_review_resolver(_reviewer, on_event=on_event)

    outcome = await run_loop(definition, review_resolver=gate)

    print("Review event stream:")
    for event in events:
        print(f"  {event.sequence}  {event.type}  {dict(event.payload)}")
    print(f"loop terminal: {outcome.terminal_event} -> {outcome.stop_reason}")
    return outcome


if __name__ == "__main__":
    anyio.run(run_demo)
