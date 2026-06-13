# Embedding LoopPlane: the host interface

Phase 2 adds a thin **host-integration layer** over the
[runtime foundation](./quickstart.md): you describe a run in one configuration
object, hand it to `LoopPlaneHost`, and the host assembles and drives the
Phase-1 runtime for you — no hand-wiring of the controller, gateway, stores, or
event sink. The host layer adds **no runtime internals of its own**; for what
each runtime component does and owns, see the Phase-1 quickstart and the
`001-loopplane-runtime-foundation` boundary table.

## A first embedded run

The scripted model ships with the runtime, so the whole path runs without any
provider credentials:

```python
import anyio

from loopplane.host import LoopPlaneHost, RuntimeConfig, ToolSpec
from loopplane.model import (
    ScriptedModel, ScriptedTurn, TextBlock, TextIncrement,
    ToolCallRequest, ToolDescriptor,
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
                    TextIncrement(text="Let me echo that."),
                    ToolCallRequest(call_id="c1", tool_name="echo",
                                    input={"text": "hello"}),
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="The tool said: hello")]),
        ],
        context_capacity=100_000,
    )

    host = LoopPlaneHost(
        RuntimeConfig(model=model, tools=(ToolSpec(ECHO, echo),))
    )

    async def on_event(event) -> None:
        print(f"{event.sequence:>3}  {event.type}")

    outcome = await host.run("please echo hello", on_event)
    print("ended:", outcome.termination_reason)


anyio.run(main)
```

`outcome` is a `RunOutcome` carrying the `session_id`, the `termination_reason`,
the number of turns, and a point-in-time `history` snapshot.

A runnable version of this is in
[`examples/host_quickstart.py`](../examples/host_quickstart.py) (also a smoke
runner: `python examples/host_quickstart.py [text|tool|durable]`). It is
developer-focused and intentionally minimal — not a product CLI.

## What the configuration selects

`RuntimeConfig` is a plain, public-safe object. Only `model` is required; every
optional subsystem defaults to off, so an otherwise-empty config behaves exactly
like the bare runtime loop.

| Field | Selects |
|---|---|
| `model` | The model provider (e.g. `ScriptedModel`, or your own boundary). **Credentials live in this object or your environment — never in the config.** |
| `tools` | Internal tools (`ToolSpec(descriptor, handler)`) registered into the Tool Gateway. |
| `tool_adapters` | Pre-built adapters (e.g. an MCP adapter) registered into the gateway. |
| `approval` | `ApprovalPolicy(allow=…, deny=…, ask=…)` per tool; enforcement stays in the Phase-1 Human Approval boundary. |
| `storage` | `StorageConfig(root=…)` — durable checkpoints **and** artifact offload, wired together automatically. |
| `memory`, `skills` | Optional memory entries and skill packages (off by default). |
| `observability` | The metadata-only telemetry overlay (off by default; requires the `otel` extra). |

A config can also be built from a plain mapping with
`RuntimeConfig.from_mapping({...})`; object-typed collaborators (the model,
handlers, adapters) pass through, scalar selections are coerced. No
configuration-file format is part of this phase.

Invalid configurations fail fast at construction — a missing model, duplicate
tool names, an approval policy naming an unregistered tool, or a selected
capability that is not installed all raise `ConfigError` before any run starts.

## Durable sessions

```python
from pathlib import Path
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig

host = LoopPlaneHost(
    RuntimeConfig(model=model, tools=(ToolSpec(ECHO, echo),),
                  storage=StorageConfig(root=Path("./loopplane-data")))
)
outcome = await host.run("do durable work", on_event)

# Later, a fresh host over the same storage rebuilds the session from records:
reopened = LoopPlaneHost(
    RuntimeConfig(model=model, storage=StorageConfig(root=Path("./loopplane-data")))
)
await reopened.resume(outcome.session_id)
```

Oversized tool outputs are offloaded to artifacts automatically; the tool result
carries a bounded preview plus a stable reference, and the full content is
retrievable with `host.retrieve_artifact(session_id, reference)`.

## Events, approvals, and the interactive round-trip

`on_event` receives every normalized runtime event in order; a consumer that
raises is isolated and recorded, never corrupting the run. To govern tools,
supply an approval handler:

```python
from loopplane.host import ApprovalDecision, ApprovalPolicy, RuntimeConfig

config = RuntimeConfig(model=model, tools=(ToolSpec(ECHO, echo),),
                       approval=ApprovalPolicy(ask=frozenset({"echo"})))

async def approve(request):
    return ApprovalDecision(allow=True)          # or allow=False to deny

outcome = await host.run("echo please", on_event, on_approval=approve)
```

For an interactive loop, open a session and drive the round-trip directly:

```python
async with host.session(on_event) as session:
    await session.submit("hello")
    session.cancel()                              # ends the run "cancelled"
    # session.answer_approval(request_id, allow=True)
    # session.answer_question(request_id, ["yes"])
```

## Phase boundary

This layer **composes** the Phase-1 runtime through its public surface and
re-implements none of it. Anything beyond host integration — a web/desktop/CLI
product, a scheduler, validator, evaluator, or any loop-automation — is out of
scope for this phase and belongs to a future-phase specification.
