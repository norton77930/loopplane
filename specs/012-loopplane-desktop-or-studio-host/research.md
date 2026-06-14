# Phase 0 Research: Desktop / Studio Host

All decisions resolve the spec's context into concrete, public-safe, offline, in-process choices. The
layer is an **additive local presentation** over the public Host Application Interface (unit 002); it
adds no runtime behavior and no third-party dependency.

## D1 — No new dependency; a console core, not a GUI

**Decision**: Ship a **developer-console core** — a command → metadata-only view-model layer — plus a
local session manager and an in-process sidecar contract, all in **pure in-process Python** over the
public host + `anyio` (already a core dependency). **No GUI, console, or other third-party framework is
introduced.**

**Rationale**: The "console" a developer interacts with is a real terminal or desktop UI shell; that
rendering layer is **reserved** (named, not built). What unit 012 owns is the deterministic core a
shell renders: structured commands in, public-safe metadata-only view models out. Keeping the GUI out
keeps the unit deterministic, offline, and in-process testable — and adds nothing to the dependency
surface (contrast unit 011, which introduced FastAPI for a network transport).

**Alternatives considered**:
- A real terminal UI (e.g. a TUI framework) or desktop GUI — pulls a heavy dependency and is not
  in-process testable/deterministic. Rejected (reserved extension point).
- Re-using unit 011's web host locally — that is a network transport (and a sibling layer the boundary
  forbids importing). Rejected; 012 embeds the host directly.

## D2 — Held-open interactive sessions via a lifespan task group

**Decision**: `StudioHost` is an **async context manager** owning an `anyio` task group and a session
registry. Opening an interactive session enters `async with host.session(...)` inside a background task
held by that group, registered by the public `session_id`; submit/answer/cancel reach the live
`Session`; closing ends the task and frees the (sequential) host.

**Rationale**: The public host exposes a session only as an `async with` context manager, so holding one
open across discrete console commands (open → submit → close) requires a background task — the same
shape as unit 011's lifespan registry. Here it is owned by the `StudioHost` the developer enters, with
**no HTTP** in between.

**Alternatives considered**:
- A per-call `async with host.session()` (not held open) — cannot satisfy "open" and "close" as
  separate commands. Rejected.

## D3 — Metadata-only view models

**Decision**: Every view the console returns is **metadata-only**: a run result view projects
`RunOutcome` to `{session_id, termination_reason, turns_taken, history, consumer_failures}` where
`history` is `[{role, block_count}]` — never the `ContentBlock` text or tool I/O. Session summaries are
`{session_id, label}`; errors/conflicts/not-found are a fixed `{kind, detail}` view.

**Rationale**: A UI shell renders these; surfacing conversation content in a summary view is an
unnecessary leak surface. `HistoryEntry.blocks` carries content, so it is projected to a count.

## D4 — Sidecar host contract + in-process implementation

**Decision**: Define a `SidecarHost` contract — a `start()` / `stop()` lifecycle plus access to the
embedded host — and ship an **in-process implementation** that wraps a `LoopPlaneHost` (start = make it
available, stop = idempotently tear down). The console reaches the host only through the contract.
**Spawning a real OS process** (an out-of-line host) is a reserved extension point.

**Rationale**: The sidecar is the seam a future real desktop app uses to host the runtime out-of-line.
Modelling it as a contract with an in-process impl gives the concept a testable, dependency-free shape
now; the real-process transport is future work.

**Alternatives considered**:
- Spawning a real subprocess now — non-deterministic, OS-dependent, not offline-testable. Rejected
  (reserved).

## D5 — Interactive approval is exercised in-process (the unit-011 lesson)

**Decision**: Because the studio is **in-process** (no network transport), the interactive
approval/question round-trip is driven and asserted directly with `anyio` — the primary flow uses an
injected `on_approval` handler on `host.session(on_approval=...)`, and out-of-band
`Session.answer_approval` is also exposed.

**Rationale**: Unit 011 learned that the buffering in-process `TestClient` / `httpx ASGITransport`
cannot read an *infinite* SSE stream incrementally, so a mid-stream out-of-band approval over HTTP was
untestable. Unit 012 has **no** transport in the way: the approval handler and the `Session` round-trip
run on the same event loop and are tested exactly as the Phase-2 host suite tests them
(`test_approval_ask_round_trips_to_host_handler`). No streaming, no buffering client.

## D6 — Boundary: `loopplane.host` only

**Decision**: `loopplane.studio` imports only `loopplane.host`, `anyio`, and the standard library. It
does **not** import `loopplane.events` — it projects `RunOutcome` (not the live event stream), and the
discard sink it passes to `host.run` is typed `Callable[[object], Awaitable[None]]`, so no event type
is named.

**Rationale**: The studio surfaces outcomes, not live events, so it needs no event serialization. The
tighter boundary (host-only) is cleaner than unit 011's (host + events + transport) and is enforced by
the import audit.

## Open questions

None. All choices are informed defaults documented in the spec's Assumptions; none is scope-blocking,
so no `[NEEDS CLARIFICATION]` markers remain.
