# Phase 1 Data Model: CLI Host

The CLI is mostly behavior; its few types live in `loopplane.cli`.

## Commands

- `loopplane chat` — interactive: read a prompt line, run it, render, repeat until
  EOF/quit.
- `loopplane run "<prompt>"` — one-shot: run a single prompt, render, exit.
- `loopplane sessions` — list durable sessions (when a store is configured).
- `loopplane resume <session_id>` — resume a durable session and continue.

Each maps to an async handler dispatched by `app.dispatch(argv)`; `main()` wraps the
dispatch in `anyio.run` and returns an exit code.

## Renderer (`render.py`)

```
class EventRenderer:                    # an EventSink
    def __init__(self, out: TextIO): ...
    async def __call__(self, event: RuntimeEvent) -> None: ...
```

Writes metadata-safe lines: assistant output text; `[tool <name>] <outcome>`; and a
final `[run <termination_reason>, <turns_taken> turn(s)]`. No raw tool I/O, secret,
or exception.

## Run core (`session.py`)

```
async def run_once(host: LoopPlaneHost, prompt: str, out: TextIO) -> RunOutcome
async def chat_loop(host: LoopPlaneHost, lines: Iterable[str] | TextIO, out: TextIO) -> None
```

`run_once` calls `host.run(prompt, on_event=EventRenderer(out))` and returns the
outcome. `chat_loop` reads prompt lines (a real stdin or a test iterable), calling
`run_once` per line until EOF/quit; it never raises on EOF/interrupt.

## Provider selection (`providers.py`)

```
def select_model(env: Mapping[str, str]) -> ModelBoundary
```

Returns the built-in scripted demo `ModelBoundary` unless `env` names an importable
builder (`LOOPPLANE_MODEL="module:function"`); then it imports and calls the builder.
A bad builder reference falls back to the scripted demo with a public-safe note. The
function never prints or echoes a credential.

## Exit codes

- `0` — success.
- `2` — usage error (missing prompt, unknown command) via `argparse`.
- `1` — an unrecoverable run surfaced as a public-safe message.

## Public surface (`__init__.py`)

`main` (the entry point) plus the testable core (`EventRenderer`, `run_once`,
`chat_loop`, `select_model`).
