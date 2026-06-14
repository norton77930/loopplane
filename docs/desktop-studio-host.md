# Desktop / Studio Host (`loopplane.studio`)

A **local, in-process developer experience** over the public Host Application Interface
([`loopplane.host`](./embedding-host.md)): a developer-console core (command → metadata-only view
model), a local session manager, and a sidecar host contract. It embeds a `LoopPlaneHost`; it drives
no runtime internals, executes no tool itself (Constitution V), and re-emits no live event bus
(Constitution VI). Unlike the web/API host (unit 011) it adds **no dependency** and ships **no GUI,
network, or OS process** — a UI shell renders the view models; the real frontend / out-of-line process
are reserved.

## The console

```python
from loopplane.studio import StudioHost

async with StudioHost(host) as studio:   # host: a LoopPlaneHost
    result = await studio.run("...")     # a one-shot run -> a RunResultView
```

`StudioHost(host)` is an async context manager that owns the task group holding interactive sessions
open. Its commands return public-safe, **metadata-only** view models (a UI shell renders them). See
[`examples/studio_quickstart.py`](../examples/studio_quickstart.py).

## Commands → view models

| Command | Does |
|---|---|
| `await studio.run(prompt)` | One-shot run → a `RunResultView` (terminal reason, turns, metadata history). Empty → `invalid`; concurrent → `conflict`. |
| `await studio.open_session(*, on_approval=None)` | Open an interactive session → its `session_id`; a second open while active → `conflict`. |
| `studio.list_sessions()` | Public-safe `SessionSummaryView`s. |
| `studio.select(session_id)` | Confirm a held session; unknown → `not-found`. |
| `await studio.submit(session_id, prompt)` | Drive the held session → its outcome view. |
| `studio.answer_approval(session_id, request_id, *, allow, scope, reason)` | Answer out-of-band → a bool; unknown session → `not-found`. |
| `studio.answer_question(session_id, request_id, answers)` | Answer out-of-band → a bool. |
| `await studio.cancel(session_id)` | Cancel + close (never hangs); unknown → `not-found`. |
| `studio.history_view(session_id)` | A metadata-only history snapshot; unknown → `not-found`. |

See [contracts/studio-api.md](../specs/012-loopplane-desktop-or-studio-host/contracts/studio-api.md).

## Interactive sessions are in-process

The interactive approval / question round-trip runs **in-process** (no transport): a session opened
with an injected `on_approval` handler is answered as the run progresses, and out-of-band
`answer_approval` / `answer_question` resolve a parked request. There is no streaming client in the
way — the round-trip is driven and tested directly on the event loop.

## Metadata-only views

Every view is metadata-only: ids, counts, public-safe reasons. A history entry is projected to
`{role, block_count}` — never the raw `ContentBlock` text or tool I/O. Errors/conflicts/not-found are a
fixed `ErrorView{kind, detail}`.

## The sidecar

```python
from loopplane.studio import InProcessSidecar

sidecar = InProcessSidecar(host)
await sidecar.start()
result = await sidecar.run("...")   # or sidecar.studio for full console access
await sidecar.stop()                # idempotent
```

`SidecarHost` is the start/stop lifecycle contract; `InProcessSidecar` is its in-process
implementation. A command before start / after stop returns an explicit `not-available` view rather
than raising. Spawning a **real OS process** (an out-of-line host) is reserved.

## Boundary

`loopplane.studio` imports only `loopplane.host` (plus `anyio` and stdlib). It never imports the
controller, gateway, dispatcher, `loopplane.events`, or a sibling layer; it executes no tool, re-emits
no live bus, spawns no process, and opens no socket. An import-boundary audit enforces it
([contracts/studio-boundary.md](../specs/012-loopplane-desktop-or-studio-host/contracts/studio-boundary.md)).

## Reserved extension points (named, not built)

A real GUI / desktop UI shell / studio frontend; OS process spawning for the sidecar and inter-process
transport; network exposure (that is unit 011); persistent studio / workspace state; multi-host pools;
any copy of a private or legacy UI.
