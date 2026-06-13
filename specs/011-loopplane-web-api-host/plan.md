# Implementation Plan: Web / API Host

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-loopplane-web-api-host/spec.md`

## Summary

Build the **Web / API Host** layer (Phase-11) that exposes the public Host Application Interface
(unit 002) over a network API: request/response endpoints to start a run and drive an interactive
session, a live **server→client event stream** of the run's normalized events, read-only inspection
endpoints (sessions, history, artifacts), and a fail-safe **authentication boundary** in front of
all of it. A new additive sub-package, `loopplane.webapi`, embeds a `LoopPlaneHost` and adapts it to
HTTP — it drives no runtime internals, executes no tool itself (Constitution V), and consumes the
normalized event stream as a host consumer without re-emitting the live bus (Constitution VI). The
chosen transport is **FastAPI / Starlette** (reusing the existing `pydantic` and `anyio` deps), with
**Server-Sent Events** for the stream and Starlette's in-process **`TestClient`** for offline tests.
Design detail lives in [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–10).

**Primary Dependencies**: the public Host Application Interface (`loopplane.host`: `LoopPlaneHost`,
`build_host`, `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`, `ToolSpec`, …) and the
public Phase-1 event serialization (`loopplane.events`: `RuntimeEvent`, `EventSink`,
`serialize_event`). **One new third-party dependency: `fastapi`** (with its bundled `starlette`),
reusing the already-present `pydantic>=2` and `anyio>=4`. Packaged as an **optional `web` extra** so
the core install is unchanged, and added to the `dev` group (with `httpx` for `TestClient`) so CI
runs the integration suite — mirroring the existing `mcp` / `otel` extra pattern. See
[research.md](./research.md) for the framework decision and alternatives.

**Storage**: None. The layer owns no store; it embeds a host and forwards calls.

**Testing**: pytest + the anyio plugin + Starlette's `TestClient` (httpx-based, **in-process, no real
socket bound** — NFR-006/NFR-007). New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. A public-safe fake model + a scripted host are the deterministic instruments
(SC-002); no real network, no external egress (FR-017).

**Target Platform**: Cross-platform ASGI application embedded in a host process; offline-testable.

**Project Type**: web-service (single backend package; **no frontend** — that is unit 012).

**Performance Goals**: Not a throughput target this phase; correctness, determinism of event order
(SC-002), and fail-safe behavior (SC-004/005) are the goals.

**Constraints**: composes only the public `loopplane.host` + `loopplane.events` surfaces (NFR-001);
executes no tool (Constitution V, NFR-002); consumes the recorded event stream, never re-emits the
live bus (Constitution VI, NFR-003); response bodies are **metadata-only** — never raw history blocks
(FR-016, NFR-006); the event stream carries `serialize_event` verbatim (FR-005); auth is **fail-safe
default-deny** and injectable (FR-013–FR-015, NFR-005); deterministic event order (NFR-004, SC-002);
offline, public-safe, English (NFR-006).

**Scale/Scope**: One new package (~6 modules), one example, one doc, unit/integration/contract
suites, one optional dependency. **No Phase-1/2/10 source is modified.**

## Dependency on Phases 1, 2 & 10

This phase is **strictly additive** and consumes only public surfaces (NFR-001, NFR-003):

- **Phase-2 host (`loopplane.host`)**: `LoopPlaneHost` / `build_host` (assemble + `run` + `session` +
  `list_sessions` + `resume` + `history_snapshot` + `retrieve_artifact`), the `Session` round-trip
  (`submit` / `answer_approval` / `answer_question` / `cancel` / `outcome`), `RunOutcome`,
  `ApprovalDecision`, and `RuntimeConfig` / `ToolSpec` for construction.
- **Phase-1 events (`loopplane.events`)**: `EventSink` (the `on_event` consumer signature),
  `RuntimeEvent` (the discriminated event union), and `serialize_event` (the public, public-safe
  serialization used for every stream frame).

The layer adds **no** new public contract to Phase-1/2; it re-exposes the host over a transport. It
re-implements no loop, no gateway, and no event bus (NFR-002, NFR-003).

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.webapi` depends on the public `loopplane.host`
and `loopplane.events`, plus the third-party transport (`fastapi` / `starlette`) and stdlib. The
runtime, loop, host, and every sibling layer have **zero** knowledge of the web layer.

```text
network client (authenticated)
     │  HTTP request/response  +  SSE event stream
     ▼
loopplane.webapi  (create_app: routes + auth boundary + SSE sink + session registry)
     │  composes ONLY the public host surface; serializes events via serialize_event
     ▼
loopplane.host.LoopPlaneHost  ──drives──▶  Phase-1 runtime (gateway owns tools; bus owns events)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/web-boundary.md](./contracts/web-boundary.md)):

- The layer **drives runs only through** `LoopPlaneHost.run` / `.session` and the `Session` handle;
  it **executes no tool** and re-implements no loop (Constitution V; NFR-002).
- It **consumes** the normalized event stream via the `on_event: EventSink` callback and forwards
  each event as `serialize_event(event)`; it **never re-emits or wraps** the live bus (Constitution
  VI; NFR-003).
- **Response bodies are metadata-only**: history is projected to `{role, block_count}` views; no
  `ContentBlock` text, tool input/output, or secret ever appears in a JSON response or error
  (FR-016; NFR-006). The **event stream** is the one surface that carries normalized content, and it
  carries only what `serialize_event` already exposes — to an authenticated client, by design
  (FR-005; Constitution VI).
- It imports only `loopplane.host`, `loopplane.events`, `fastapi` / `starlette`, and stdlib; it does
  **not** import the controller, gateway, dispatcher, or a sibling layer (NFR-001).

## Project Structure

### Documentation (this feature)

```text
specs/011-loopplane-web-api-host/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── web-api.md         # endpoints, request/response shapes, SSE frames, status codes
│   └── web-boundary.md    # the host-only / metadata-only / no-tool / default-deny boundary + audit
├── checklists/requirements.md
└── tasks.md               # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/webapi/
├── __init__.py        # public exports: create_app + Authenticator/AuthResult + request/response models
├── app.py             # create_app(host, *, authenticator=None, api_prefix="/v1") -> FastAPI; routes + lifespan
├── auth.py            # Authenticator protocol, AuthResult, deny-all default, fail-safe auth dependency (FR-013-FR-015)
├── models.py          # pydantic request/response models — metadata-only, public-safe (FR-016, NFR-006)
├── streaming.py       # SSE event sink + frame formatting over serialize_event; fail-safe consumer (FR-004-FR-006)
└── sessions.py        # interactive session registry: background-held host.session + out-of-band answers (FR-007-FR-010)

examples/
└── webapi_quickstart.py   # runnable: build host -> create_app -> TestClient drives run + stream + auth (public-safe, in-process)

docs/
└── web-api-host.md        # public-safe guide: endpoints, event stream, auth boundary, embedding

tests/
├── unit/
│   └── test_webapi_core.py        # metadata-only history projection, error envelope, deny-all default
├── integration/
│   ├── test_webapi_us1.py         # US1: POST /runs -> public-safe outcome; concurrent -> 409; malformed -> 4xx (SC-001)
│   ├── test_webapi_us2.py         # US2: SSE stream order == serialize_event recorded order; disconnect safe (SC-002/005)
│   ├── test_webapi_us3.py         # US3: open session, submit, answer approval out-of-band, cancel never hangs
│   ├── test_webapi_us4.py         # US4: list/history/resume/artifact; unknown id -> not-found; metadata-only (SC-003)
│   └── test_webapi_us5.py         # US5: default-deny, valid pass-through, raising authenticator denied (SC-004)
└── contract/
    └── test_webapi_boundary.py    # import-boundary (host/events/fastapi/stdlib only), no gateway/controller, no tool exec, response metadata-only (SC-003/006)
```

**Structure Decision**: one new sub-package `loopplane.webapi`, mirroring the Phase-1..10
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently
revertible addition. It depends inward on the public `loopplane.host` + `loopplane.events` surfaces
and on the `fastapi` transport (optional `web` extra). No Phase-1/2/10 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks
are deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| IA — Foundational + run (US1) | package skeleton + `__init__`; `models.py` (`RunRequest`, `RunResult`, `HistoryEntryView`, `ErrorResponse`); `auth.py` deny-all default + dependency; `app.py` `create_app` + `POST /runs`; `pyproject` `web` extra + dev deps — **blocks all stories** | `test_webapi_core.py` + `test_webapi_us1.py` green; metadata-only outcome; concurrent → 409; malformed → public-safe 4xx (SC-001) | Revert package + pyproject |
| IB — Event stream (US2) | `streaming.py` (SSE sink over `serialize_event`) + `POST /runs/events` | `test_webapi_us2.py` green; stream order == recorded order; disconnect never crashes the run (SC-002/005) | Revert IB |
| IC — Interactive session (US3) | `sessions.py` (registry, background-held `host.session`) + open/submit/answer-approval/answer-question/cancel/events routes | `test_webapi_us3.py` green; out-of-band approval resolves; cancel never hangs | Revert IC |
| ID — Inspection (US4) | list / history / resume / artifact routes, metadata-only projection | `test_webapi_us4.py` green; unknown id/reference → explicit not-found; no raw blocks (SC-003) | Revert ID |
| IE — Auth boundary (US5) | the auth dependency enforced on every route; default-deny; raising authenticator denied | `test_webapi_us5.py` green; missing/invalid/raising → denied; valid → admitted (SC-004) | Revert IE |
| IF — Example, docs, boundary | `examples/webapi_quickstart.py`, `docs/web-api-host.md`, `test_webapi_boundary.py` + public-safety `PHASE11_TARGETS` | boundary + metadata-only + no-tool-exec green; example runs in-process; scan clean (SC-003/006) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Leaking conversation content in a **response** body (history blocks) | Response bodies are metadata-only projections (`{role, block_count}`, ids, reasons); a unit test asserts no `ContentBlock` text appears in any JSON response (FR-016, NFR-006, SC-003). The **event stream** intentionally carries normalized events verbatim (Constitution VI) — the authenticated client receiving the run's own output is by design, not a repo/secret leak (Principle VII governs committed artifacts, which use only public-safe fixtures) |
| Leaking internal detail in an **error** | Every error returns a fixed public-safe envelope (`{detail}`); no stack trace, internal type name, or filesystem path; a test drives malformed/unknown inputs and asserts clean envelopes (FR-016, SC-003) |
| A disconnecting / failing stream client crashing or hanging the run | The SSE sink is fail-safe: a broken send channel is swallowed and recorded as a consumer failure; the run still terminates; a test disconnects mid-stream (FR-006, NFR-005, SC-005) |
| Auth bypass / fail-open | The default authenticator denies all; the dependency denies on a missing, malformed, **or raising** authenticator before reaching the host; tests cover all three and a valid pass-through (FR-013–FR-015, NFR-005, SC-004) |
| Executing a tool / re-emitting the live bus (Constitution V/VI breach) | The layer only calls `host.run` / `host.session` / the `Session` handle and consumes `on_event`; a contract test asserts no gateway/controller import, no tool execution, and no live-bus emission (NFR-002/003, SC-006) |
| Concurrent run on a sequential host | The host is sequential per instance; a second run/session while active is mapped from the host's `RuntimeError` to an explicit **409 Conflict**, never corrupting state (FR-003) |
| New dependency bloating the core install | `fastapi` is an **optional `web` extra**; the core install is unchanged; only the dev group adds it (+ `httpx`) for CI — mirroring `mcp` / `otel` |
| Reaching a runtime internal through transport internals | Import-boundary audit restricts imports to `loopplane.host` / `loopplane.events` / `fastapi` / `starlette` / stdlib; references no controller / gateway / dispatcher token (NFR-001) |
| Scope creep into a UI / cloud deploy / multi-tenant auth | Out-of-scope list + reserved extension points; Constitution III gate; this phase ships only the network API, SSE stream, auth boundary, in-process tests, an example, and a doc |

**Rollback posture**: `loopplane.webapi` is purely **additive** over Phases 1, 2 & 10 — small,
task-scoped commits, each phase (IA–IF) independently revertible. The layer owns no runtime state and
drives nothing of its own, so reverting any or all (and dropping the optional `web` extra) leaves the
runtime, host, and every sibling untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.webapi` written fresh; composes the public host + event surfaces; no legacy code copied |
| III | Agent Harness Before Loop Automation | PASS | An additive transport over the existing host; ships **no** UI, no scheduler/validator/loop automation, and names every reserved extension point |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (adapt the public host to HTTP); depends inward on public surfaces; no run/gateway/bus logic of its own |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes **no** tool; tool execution remains the gateway's, reached only through `LoopPlaneHost` (NFR-002; contract-tested) |
| VI | Runtime Event Bus Ownership | PASS | **Central**: the layer is a streaming **consumer** of recorded normalized events; it forwards `serialize_event(event)` and never formats frontend events on the bus, re-emits, or wraps it (FR-005, NFR-003) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names/IPs in any artifact; committed code/tests/example/doc use public-safe fixtures; response bodies are metadata-only; scan extended with PHASE11 targets (NFR-006, SC-003/006) |
| VIII | No SDK Replacement | PASS | `fastapi`/`starlette` is a **web transport** for an additive host layer — **not** the runtime core. It replaces no Agent Loop / Controller / Dispatcher / Tool Gateway / Event Bus (those stay LoopPlane's, reached only through the public host). Principle VIII forbids replacing the runtime **core** with an *agent* framework (LangGraph/LangChain/CrewAI/AutoGen/Agents SDK); a transport framework is outside that prohibition. See Complexity Tracking + research.md |
| IX | Reference, Not Clone | PASS | Endpoint/stream/auth shapes re-derived public-safe from the spec and the public host surface; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (IA–IF) has required tests, a validation gate, and a rollback note; the package + optional extra are additive and revertible; determinism (SC-002) + fail-safe (SC-004/005) + metadata-only (SC-003) first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and
no Phase-1/2/10 modification. The one notable decision (a new transport dependency) is recorded in
Complexity Tracking and research.md; it is an optional extra and replaces no runtime component.

## Complexity Tracking

> The single decision worth justifying is the new third-party transport dependency. It is **not** a
> constitution violation (Principle VIII targets the runtime core, not transport), but it is the most
> scrutiny-worthy choice, so it is recorded here for the review gate.

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| Add `fastapi` (optional `web` extra) | A web/API host needs HTTP routing, request validation, SSE streaming, an injectable auth seam, and an in-process test client — building these on stdlib alone reinvents a large, error-prone surface (esp. validation/error hygiene for FR-016 and offline testing for NFR-007) | A hand-rolled stdlib ASGI/`http.server` host was rejected: more code, weaker error hygiene (leak risk), no typed request validation, no in-process `TestClient`. Starlette-alone was rejected: it drops the pydantic-based validation/error model the project already depends on. FastAPI reuses the existing `pydantic`+`anyio` deps and is the board-sanctioned default ("FastAPI or equivalent") |
