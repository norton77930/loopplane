# Contract: Host Interface Integration (Boundary)

**Feature**: `003-loopplane-loop-engineering-layer` | FR-080–FR-083, FR-090–FR-092, NFR-003

This is the **boundary contract** that keeps the Loop Engineering Layer strictly above the runtime. Every
Agent Run the layer starts, drives, or observes goes through the Phase-2 Host Application Interface and
its normalized event stream — never through reach-through internal access (NFR-003, SC-002).

## The only allowed Phase-2 surface

The loop layer consumes **exactly** these `loopplane.host` members and nothing deeper:

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig, RunOutcome, ApprovalDecision
# value types from the host's own re-exports / Phase-1 event vocabulary:
from loopplane.events import RuntimeEvent            # consumed via host.run(on_event=...)
```

| Call | Used for | Requirement |
|---|---|---|
| `LoopPlaneHost(config)` / `host_profile.build()` | one host per Loop Run, built from the definition's host profile | FR-002, FR-080 |
| `await host.run(prompt, on_event, *, on_approval=)` | start exactly one Agent Run per iteration | FR-011, FR-080 |
| `RunOutcome.session_id`, `.termination_reason` | the iteration's run reference + terminal reason (read-only) | FR-012, FR-083 |
| `on_event: EventSink` | consume the normalized Runtime Event stream for the run | FR-012, FR-081 |
| `host.retrieve_artifact(session_id, ref)` | resolve a reused artifact by reference (repair) | FR-053, FR-083 |
| `host.history_snapshot(session_id)` | reference-only history access for Loop State | FR-061, FR-083 |
| `on_approval` / `ApprovalDecision` | surface in-run tool approval to the Phase-1 boundary | FR-082 |

## Prohibitions (FR-081, FR-090)

The loop layer MUST NOT:

- import or call `loopplane.controller` (`RuntimeController`, `Dispatcher`), `loopplane.gateway`,
  `loopplane.loop` (Agent Loop), `loopplane.events.EventEmitter`/bus, `loopplane.memory`,
  `loopplane.checkpoint`, `loopplane.artifacts`, `loopplane.approval`, or `loopplane.observability`
  **directly** for run orchestration (FR-081, FR-090);
- start, drive, or terminate an Agent Run by any path other than `host.run` / `host.session` (FR-080);
- re-implement or duplicate any Phase-1 runtime internal or Phase-2 host-assembly internal (FR-090);
- subscribe to the Phase-1 Runtime Event Bus, Dispatcher, or Agent Loop directly (FR-081);
- implement any out-of-scope product layer — web UI, desktop app, browser frontend, distributed
  scheduler, queue worker, cloud deployment, multi-user tenancy, plugin marketplace, full multi-agent
  orchestration, sandboxed execution, cost governance, or external DB persistence (FR-092).

> Reading Phase-1 **value types** that the host re-exposes (e.g. `RuntimeEvent`, `TerminationReason`,
> `ContentBlock`/`TextBlock`, `ApprovalRequestedPayload`) is permitted — these are the normalized data
> the host hands out, not reach-through orchestration. The line is: **data in/out through the host = OK;
> driving runtime components = prohibited.**

## Reserved extension points (named, not built) — FR-091

- Interval and condition trigger **execution** (a production scheduler/watcher).
- Durable loop-state persistence and **loop resume**.
- Multiple concurrent Loop Runs (single in-process Loop Run this phase).
- Full multi-agent orchestration.

## Auditability (NFR-003, SC-002, SC-010)

- A boundary-audit test MUST assert the `loopplane.engineering` package imports **only** the allowed
  surface above — failing if any prohibited Phase-1/2 internal is imported (NFR-003, SC-002).
- 100% of Agent Runs started by loops in the test suite MUST go through `host.run` / `host.session`; no
  test or audit may demonstrate any other path (SC-002).
- A public-safety scan over committed Phase-3 files MUST find zero private references and confirm no
  Phase-1/2 internal is re-implemented (SC-010, NFR-004).
