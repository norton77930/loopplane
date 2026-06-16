# Embedding LoopPlane: Quickstart

LoopPlane is an embeddable agent-harness runtime: you bring a model and a
host process; the runtime drives the conversation loop, governs every tool
call through one gateway, emits a normalized event stream, and (optionally)
persists sessions so they survive a crash.

## Install

```sh
pip install loopplane            # core: anyio + pydantic + jsonschema
pip install "loopplane[mcp]"     # + external MCP tool servers
pip install "loopplane[otel]"    # + the observability overlay
```

## A first run

The scripted model substitute ships with the runtime, so the full loop runs
without any provider credentials:

```python
import anyio
from pathlib import Path

from loopplane.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

ECHO = ToolDescriptor(
    name="echo",
    description="Echo the given text back.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)


async def echo(call_input, context):
    return [TextBlock(text=str(call_input["text"]))]


async def main() -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    TextIncrement(text="Let me try the echo tool."),
                    ToolCallRequest(
                        call_id="c1", tool_name="echo", input={"text": "hello"}
                    ),
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="The tool said: hello")]),
        ],
        context_capacity=100_000,
    )

    gateway = ToolGateway()
    gateway.register(ECHO, echo)

    async def print_event(event):
        print(f"{event.sequence:>3}  {event.type}")

    controller = RuntimeController(
        model=model, gateway=gateway, event_sink=print_event
    )
    session_id = controller.create_session(working_scope=Path.cwd())
    await controller.drive(session_id, [TextBlock(text="please echo hello")])

    for entry in controller.history_snapshot(session_id):
        print(f"history: {entry.role} ({len(entry.blocks)} block(s))")


anyio.run(main)
```

Running it prints the normalized event sequence — `user-input`, the
assistant increments, `turn-completed`, the `tool-call-*` pair, and exactly
one `run-terminated` — followed by the four recorded history entries.

## What you wire together

| Piece | Role |
|---|---|
| `ModelBoundary` | The one model-facing seam: `stream_turn(request)` yields text/reasoning/tool-call increments and a turn end; `context_capacity()` answers the token budget. Implement it for your provider, or use `ScriptedModel` in tests. |
| `ToolGateway` | The single chokepoint for every tool call: resolve, validate (undeclared parameters are always rejected), decide, execute under a time limit, normalize, size-manage. Register plain handlers or adapters. |
| `HumanApproval` | Optional decide-stage policy: persistent allow/deny rules, session-scoped approval memory, reviewer escalation. Without it the gateway allows everything (test posture). |
| `RuntimeController` | Session lifecycle: create, drive, attach, detach, resume, terminate, list. |
| `Dispatcher` | Drives the round-trip over abstract channels for hosts: submit-input, cancel, approval decisions, question answers. |

## Durable sessions

```python
from loopplane.artifacts import ArtifactStore, make_artifact_handoff
from loopplane.checkpoint import FileCheckpointStore

storage = Path("./loopplane-data")
artifacts = ArtifactStore(storage)
gateway = ToolGateway(artifact_handoff=make_artifact_handoff(artifacts))
controller = RuntimeController(
    model=model,
    gateway=gateway,
    event_sink=print_event,
    checkpoint_store=FileCheckpointStore(storage),
    artifact_store=artifacts,
)
```

Every accepted input, assistant message, tool result, and termination is
appended durably as it occurs. In a later process:

```python
await controller.resume(session_id)   # rebuild from records alone
await controller.attach(session_id)   # replay history as events (replay: true)
await controller.drive(session_id, [TextBlock(text="continue where we left off")])
```

Interrupted tool calls are repaired with error-marked synthetic results and
surfaced as `diagnostic` warnings; oversized tool outputs are preserved in
full as artifacts and retrievable by the stable reference carried in the
tool result.

## Memory, skills, and observability

All optional, all off by default, and provably zero-behavior-change when
disabled:

```python
from loopplane.memory import MemoryStore
from loopplane.skills import SkillToolAdapter, load_skills, skill_profiles
from loopplane.approval import HumanApproval

skills, problems = load_skills([Path("./skills")])
gateway.register_adapter(SkillToolAdapter(skills))
controller = RuntimeController(
    model=model,
    gateway=ToolGateway(decide=HumanApproval(skill_profiles=skill_profiles(skills))),
    event_sink=print_event,
    memory_store=MemoryStore(Path("./memory")),
    skills=skills,
)
```

For telemetry, install `loopplane[otel]`, set `OTEL_EXPORTER_OTLP_ENDPOINT`,
and wrap your sink with `loopplane.observability.maybe_attach(sink)` — spans
and metrics are strictly metadata-only.

## Going further

- `examples/run_summary_consumer.py` — a future-layer consumer built on the
  public extension surface only.
- `docs/real-model-validation.md` — the manual procedure for validating a
  real model integration behind the model boundary.
