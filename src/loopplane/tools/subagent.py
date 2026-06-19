"""The Subagent Spawn Tool Adapter (spec 043): a model-driven, one-shot subagent.

``spawn_subagent`` lets the model delegate a focused sub-task to ONE bounded child
agent. The child is driven through the **existing** public Phase-3 loop entry point
(``loopplane.engineering.run_loop`` — the same seam unit-013's host-driven coordinator
composes), so this adapter re-implements no agent loop. It returns the child's final
assistant text to the parent as a normalized tool result.

It is additive, reuse-first, and SAFE:

- **Hard recursion-depth cap (fail-safe)**: the adapter is built with the configured
  ``max_subagent_depth`` and reads the per-run ``RunContext.subagent_depth`` the Tool
  Gateway already hands to every tool. When ``subagent_depth >= max_subagent_depth`` it
  DENIES the call with a normalized error and starts **no** child run, so subagents
  cannot nest without bound. A child runs at ``parent.subagent_depth + 1``.
- **Failure containment** (mirrors the 013 coordinator): a child that raises, fails to
  complete, pauses, or produces no answer maps to a normalized ``ErrorOutput`` (a fixed
  public-safe marker — never a raw exception, stack trace, secret, or private path); the
  parent run continues.
- **Events** (Constitution VI): the child run is driven with **no** live event sink, so
  the child's events are captured in its ``LoopOutcome`` and never re-emitted onto the
  parent's live bus; only a metadata-only event count (via the 013 ``aggregate_events``
  view) is surfaced.

This adapter executes no tool itself: the child's tools run only through the child's own
Tool Gateway (its ``LoopPlaneHost``). It is reachable only through the Gateway
(Constitution V).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from loopplane.context import RunContext
from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopOutcome,
    LoopState,
    ManualTrigger,
    ObservationPolicy,
    StaticInput,
    ValidationPolicy,
    ValidationResult,
    max_iterations,
    run_loop,
)
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.orchestration import (
    ChildRunReference,
    SubagentResult,
    aggregate_events,
)

if TYPE_CHECKING:
    from loopplane.host import LoopPlaneHost


# Builds a fresh child ``LoopPlaneHost`` for a one-shot subagent run: the child depth
# (parent + 1), an optional restricted tool allowlist, and the working scope to inherit.
# Injected by the host assembly (``host/assembly.py``) so this module never imports the
# host facade at runtime (no ``tools -> host`` cycle); typed here under TYPE_CHECKING.
ChildHostFactory = Callable[[int, "tuple[str, ...] | None", Path], "LoopPlaneHost"]


_SPAWN_DESCRIPTOR = ToolDescriptor(
    name="spawn_subagent",
    description=(
        "Delegate a focused sub-task to a one-shot child agent: it runs once to "
        "completion and returns its final answer. Use for a self-contained sub-task "
        "(e.g. research or a summary). The child runs a single bounded turn-cycle and "
        "cannot run indefinitely or spawn other agents without bound. Pass the task as "
        "text; optionally restrict the child's tools with allowed_tools."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "allowed_tools": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task"],
        "additionalProperties": False,
    },
    # Not read-only: the child agent may use non-read-only tools. Not a network tool
    # itself (the child's own tools carry their own flags).
)


def _always_pass(outcome: object, state: LoopState) -> ValidationResult:
    """A trivial validator: a one-shot child's natural completion is a pass, so the
    loop terminates ``loop_completed`` after its single iteration (the orchestration
    test harness uses the same always-pass posture)."""

    return ValidationResult(status="pass", reason="subagent completed")


def _final_assistant_text(history: Sequence[object]) -> str:
    """The child's final assistant message text: the joined ``TextBlock`` text of the
    last assistant history entry (empty when the child produced no assistant text)."""

    for entry in reversed(list(history)):
        role = getattr(entry, "role", None)
        if role != "assistant":
            continue
        blocks = getattr(entry, "blocks", ())
        text = "".join(block.text for block in blocks if isinstance(block, TextBlock))
        return text.strip()
    return ""


class SpawnSubagentAdapter:
    """A Tool Gateway adapter exposing the single ``spawn_subagent`` tool (spec 043)."""

    def __init__(
        self,
        *,
        build_child_host: ChildHostFactory,
        max_subagent_depth: int,
    ) -> None:
        self._build_child_host = build_child_host
        self._max_subagent_depth = max_subagent_depth

    def describe(self) -> Sequence[ToolDescriptor]:
        return [_SPAWN_DESCRIPTOR]

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        async for output in self._spawn(call_input, context):
            yield output

    async def shutdown(self) -> None:
        return None

    async def _spawn(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        # --- Recursion guard (fail-safe): deny at/over the cap BEFORE any child run.
        if context.subagent_depth >= self._max_subagent_depth:
            yield ErrorOutput(
                category=ErrorCategory.POLICY_DENIAL,
                message=(
                    f"subagent depth cap reached "
                    f"({self._max_subagent_depth}); refusing to spawn a subagent"
                ),
            )
            return

        task = str(call_input["task"])
        allowed_tools = _coerce_allowed_tools(call_input.get("allowed_tools"))
        child_depth = context.subagent_depth + 1
        working_scope = context.working_scope

        # The child host is built lazily by the loop definition's selector so we can
        # capture the constructed host and read its final history snapshot afterwards.
        holder: dict[str, LoopPlaneHost] = {}

        def selector() -> LoopPlaneHost:
            host = self._build_child_host(child_depth, allowed_tools, working_scope)
            holder["host"] = host
            return host

        definition = LoopDefinition(
            loop_id=f"subagent-{uuid.uuid4().hex}",
            trigger=ManualTrigger(),
            input_source=StaticInput(task),
            host_profile=HostRuntimeProfile(selector=selector),
            validation_policy=ValidationPolicy(validator=_always_pass),
            # One-shot: exactly one iteration, stop on the (always-pass) validation.
            stop_condition=max_iterations(1),
            observation_policy=ObservationPolicy(emit_loop_events=True),
        )

        # Drive the child through the EXISTING public Phase-3 entry point with NO live
        # sink (Constitution VI): the child's events stay captured in the outcome.
        try:
            outcome = await run_loop(definition)
        except Exception:  # noqa: BLE001 - fail safe, mirror the 013 coordinator
            yield ErrorOutput(message="subagent run failed")
            return

        # A child that did not complete naturally (failed validation, non-natural
        # termination, or paused for review) is contained as a normalized error.
        if outcome.terminal_event != "loop_completed" or outcome.paused:
            yield ErrorOutput(
                message=(
                    f"subagent did not complete ({outcome.stop_reason or 'no result'})"
                )
            )
            return

        host = holder.get("host")
        text = _recover_final_text(host, outcome)
        if not text:
            yield ErrorOutput(message="subagent produced no answer")
            return

        # Surface the child's events as METADATA ONLY (reuse the 013 aggregation), never
        # the payloads/content and never on the parent's live bus.
        summary = _child_event_summary(outcome)
        yield TextBlock(text=f"{text}\n\n{summary}")


def _coerce_allowed_tools(raw: object) -> tuple[str, ...] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    return None


def _recover_final_text(host: LoopPlaneHost | None, outcome: LoopOutcome) -> str:
    """Read the child's final assistant text from the child host's history snapshot for
    the child run's session (the public host surface; ``LoopOutcome`` does not carry the
    conversation, so we recover it from the captured run reference)."""

    if host is None or not outcome.state.run_refs:
        return ""
    session_id = outcome.state.run_refs[-1].session_id
    try:
        history = host.history_snapshot(session_id)
    except KeyError:
        return ""
    return _final_assistant_text(history)


def _child_event_summary(outcome: LoopOutcome) -> str:
    """A metadata-only, public-safe one-liner about the child's captured loop events
    (count + terminal), via the unit-013 ``aggregate_events`` view — no payloads."""

    reference = ChildRunReference(
        subagent="subagent",
        loop_id=outcome.loop_id,
        run_refs=outcome.state.run_refs,
    )
    result = SubagentResult(
        subagent="subagent", reference=reference, outcome=outcome, failure=None
    )
    events = aggregate_events([result])
    return f"[subagent completed: {len(events)} loop events]"
