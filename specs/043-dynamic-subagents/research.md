# Phase 0 Research: Dynamic Subagents (043)

Grounded in the real code (the riskiest unit). Every decision below was verified by reading the seams,
not assumed.

## Decision 1 — Reuse the public Phase-3 `run_loop` to drive the child (no loop rewrite)

**Finding (verified)**: `loopplane.engineering.controller.run_loop(definition, *, on_loop_event=None,
on_approval=None, review_resolver=None) -> LoopOutcome` builds a `LoopController`, which builds a host
from `definition.host_profile.build()` and drives it via `host.run(prompt, sink, ...)` under a hard
iteration bound. Unit-013's `Coordinator._run_subagent` composes **exactly** this:

```python
try:
    outcome = await run_loop(definition)        # the ONLY child-driving call
except Exception:
    return SubagentResult(..., failure="failed")  # fail-safe containment
```

A subagent is a `LoopDefinition` whose `HostRuntimeProfile(selector=...)` builds a `LoopPlaneHost` over a
model (verified in `tests/orchestration_helpers.py::scripted_subagent_definition`).

**Decision**: The `spawn_subagent` tool builds a **one-shot** `LoopDefinition` (a `ManualTrigger`,
`StaticInput(task)`, a `HostRuntimeProfile` selector building a depth-incremented child host, an
always-pass `ValidationPolicy`, `stop_on_pass()` + `max_iterations(1)`,
`ObservationPolicy(emit_loop_events=True)`) and calls **`run_loop(definition)`** — the same public entry.
No new loop, no controller change, no orchestration-core change.

**Rejected**: calling `host.run()` directly from the tool (skips the Phase-3 loop layer the brief
requires reusing) and re-implementing a turn cycle (forbidden — IV/NFR-001).

## Decision 2 — Where the tool lives: the `tools` layer, NOT `loopplane.orchestration`

**Finding (verified)**: `specs/013-.../contracts/orchestration-boundary.md` +
`tests/contract/test_orchestration_boundary.py` impose a **strict import allow-list** on
`loopplane.orchestration`: it may import **only** `loopplane.engineering` + stdlib, and **must not**
import `loopplane.host`, `loopplane.gateway`, `loopplane.controller`, `loopplane.context`,
`loopplane.events`, `loopplane.model`, etc. A Gateway tool needs `loopplane.gateway.spi` (`ToolAdapter`,
`ErrorOutput`), `loopplane.context` (`RunContext`), and `loopplane.model` (`ToolDescriptor`, `TextBlock`)
— all forbidden there.

**Decision**: Put the tool in **`src/loopplane/tools/subagent.py`** (next to `internal.py` / `web.py`).
The `tools` layer already imports the gateway, model, context, events, approval, and memory; it has **no
import-boundary audit**, and importing `loopplane.engineering` from it is allowed. The tool **reuses**
the orchestration package from the allowed direction (`from loopplane.orchestration import
aggregate_events`) for the metadata-only events view. This keeps the orchestration core pure (its
boundary test stays green) and keeps Constitution IV intact.

**Rejected**: putting the tool in `loopplane.orchestration` (would break its boundary audit) or in
`loopplane.host` (would couple a tool to the host facade; the `tools` layer is the established home for
tool adapters).

## Decision 3 — The recursion guard: an additive `RunContext.subagent_depth` + a config cap, enforced at the Gateway

**Finding (verified)**:
- The Gateway hands the **same per-run `RunContext`** to every tool: `tool.adapter.invoke(call.tool_name,
  dict(effective_input), context)` (`gateway/gateway.py`). So a tool can read per-run state from
  `context`.
- `RunContext` is constructed in **exactly one place**: `RuntimeController.drive()` (the comment on the
  controller says so, verified). It is built fresh per `drive()` with the session's fields and always
  `subagent_depth` would default to 0 unless the controller is told otherwise.
- The host → controller path: `assemble(config)` builds `RuntimeController(model=config.model,
  gateway=gateway, event_sink=sink, plan_mode=config.plan_mode, ...)`. Adding an additive defaulted
  controller kwarg + a `RuntimeConfig` field is the established additive pattern (verified against the
  `plan_mode` precedent end-to-end).

**Decision**:
- Add **`RunContext.subagent_depth: int = 0`** (additive, default 0 — top-level).
- Add **`RuntimeConfig.max_subagent_depth: int = 0`** (additive; `from_mapping` coercion;
  `validate_config` requires `>= 0`). **Default `0` is off** — `assemble` registers the tool only when
  `>= 1`, so an existing runtime that does not opt in is byte-identical to today (consistent with the
  `plan_mode` / `allow_network` default-off precedent). A host sets it to `1` to enable exactly one
  level.
- Thread depth: add **`RuntimeController(subagent_depth: int = 0)`**; `drive()` builds
  `RunContext(subagent_depth=self._subagent_depth, ...)`. `assemble` passes `config.max_subagent_depth`
  as a *cap* to the adapter and the controller's *current* depth as the per-run depth (top-level = 0;
  the child host is assembled at parent+1 by the child-config factory — Decision 5).
- The adapter is built with the cap and, on invoke, **denies** with `ErrorOutput` (and starts **no**
  child run) when `context.subagent_depth >= max_subagent_depth`. The child runtime is built at
  `subagent_depth = context.subagent_depth + 1`, so the child's own `spawn_subagent` is capped one level
  deeper. This is fail-safe: the deny is the default outcome at the boundary; no run is created.

**Rejected**: a process-global depth counter (not per-run, races across sessions) and enforcing the cap
in a `PolicyDecider` (the decider does not build the child run; the tool both checks and builds, so the
check belongs in the tool, which is still at the Gateway boundary — consistent with how `exit_plan_mode`
mutates run state inside the tool).

## Decision 4 — Recovering the child's final assistant text

**Finding (verified)**: `run_loop` returns a `LoopOutcome` that carries `state` (run refs, artifacts) and
`events`, but **not** the conversation history / final assistant text — `LoopController._start_agent_run`
calls `host.run(...)` and keeps only `RunReference(session_id, termination_reason)` in
`state.run_refs`. The final text lives in `RunOutcome.history` (a `tuple[HistoryEntry, ...]`), and the
host exposes `host.history_snapshot(session_id) -> tuple[HistoryEntry, ...]`. A `HistoryEntry` has
`role: "user"|"assistant"` and `blocks`; assistant text is the `TextBlock`s of the last assistant entry.

**Decision**: The child-host factory hands the constructed `LoopPlaneHost` back to the adapter (the
selector captures it in a holder). After `run_loop` returns, the adapter reads
`host.history_snapshot(outcome.state.run_refs[-1].session_id)`, takes the **last** assistant entry, joins
its `TextBlock` texts, and returns that as a `TextBlock`. An empty/absent answer → a clear normalized
result (FR-020).

**Rejected**: changing `LoopOutcome` to surface the final text (a Phase-3 contract change — avoided; the
public host surface already exposes the history snapshot).

## Decision 5 — Wiring the child runtime additively (the child-config factory)

**Finding (verified)**: `RuntimeConfig` carries `model: ModelBoundary`, `tools: tuple[ToolSpec, ...]`,
`tool_adapters: tuple[ToolAdapter, ...]`, plus the opt-in flags. A child host is just
`LoopPlaneHost(child_config)`. To build a child at depth+1, the child host's controller must start its
`RunContext` at that depth.

**Decision**: In `assemble`, when `config.max_subagent_depth >= 1`, construct a `SpawnSubagentAdapter`
with: (a) the parent `model`; (b) a **child-config factory** `Callable[[int, tuple[str, ...] | None],
RuntimeConfig]` that returns a copy of the parent `RuntimeConfig` with the spawn adapter **removed from
the child's `tool_adapters`** unless still allowed (and the child's depth carried via a small additive
field; see below), optionally filtered to `allowed_tools`; and (c) the cap. The adapter builds the child
host as `LoopPlaneHost(child_config)` and, crucially, the child host's controller must run at depth+1.

Because the per-run depth is set by the controller, the cleanest additive thread is: the child host is
built from a child `RuntimeConfig`, and `assemble` constructs the **child** controller with
`subagent_depth = parent_depth + 1`. Since `assemble` only knows `config.max_subagent_depth` (the cap),
not the *current* depth, the depth is carried by the adapter (which knows `context.subagent_depth` at
invoke time): the adapter builds the child host directly via an injected factory `build_child_host(depth:
int, allowed_tools) -> LoopPlaneHost` that calls `assemble`/`LoopPlaneHost` with the child controller
depth set to `depth`. To avoid `tools → host` runtime coupling, `assemble` (in the host layer) supplies
this `build_child_host` closure to the adapter at construction; the adapter holds it as an opaque
callable typed under `TYPE_CHECKING`.

**Net**: `assemble` passes the adapter both the cap and a `build_child_host(depth, allowed_tools)` closure
(which re-enters `assemble` with the child config + the child controller depth). The adapter calls
`build_child_host(context.subagent_depth + 1, allowed_tools)` inside the one-shot definition's selector.

**Rejected**: giving the adapter the parent `ToolGateway`/`RuntimeController` directly (the parent
controller has an active session/sink; the child needs its own fresh host) and importing `host` at module
scope in `tools` (a cycle — solved with the injected closure + `TYPE_CHECKING` typing).

## Decision 6 — Events handling: capture, never re-emit (Constitution VI)

**Finding (verified)**: Unit-013's coordinator passes **no live sink** to `run_loop` and reads the
captured `LoopOutcome.events`; `aggregate_events(results)` projects them to metadata-only
`(subagent, type, sequence)`. The orchestration boundary contract makes "re-emits no live bus" an
enforced rule.

**Decision**: The adapter passes **no `on_loop_event`** to `run_loop`, so the child's events are captured
in the `LoopOutcome` and never touch the parent's live bus. The adapter reuses
`loopplane.orchestration.aggregate_events([SubagentResult(...)])` (wrapping the child outcome in a
`SubagentResult`) to surface a **metadata-only event count** as a short diagnostic line in the result —
no payloads, no conversation content. The parent's own `spawn_subagent` call still emits the ordinary
`tool-call-started`/`tool-call-completed` events the Gateway already produces; no event-schema change, no
`SCHEMA_VERSION` bump.

## Decision 7 — Failure containment + boundedness

**Finding (verified)**: the Gateway wraps `adapter.invoke(...)` in `try/except` (→ a normalized
`EXECUTION` error) **and** in `anyio.move_on_after(call_timeout_seconds)` (→ a normalized `TIMEOUT`
error). The child loop is bounded to one iteration (`max_iterations(1)`).

**Decision**: The adapter itself wraps `run_loop` in `try/except` (mirror 013) and inspects the outcome:
a non-`loop_completed` terminal, a paused outcome, a raise, or an empty answer all map to a normalized
`ErrorOutput` (fixed public-safe markers, never a raw exception). Defense in depth: even if the adapter
missed a case, the Gateway's `invoke` guard + per-call timeout still contain it. The parent run continues
either way.

## Summary of touched files (all additive)

| File | Change |
|---|---|
| `src/loopplane/context.py` | + `RunContext.subagent_depth: int = 0` |
| `src/loopplane/tools/subagent.py` | NEW `SpawnSubagentAdapter` (one tool) |
| `src/loopplane/tools/__init__.py` | export `SpawnSubagentAdapter` |
| `src/loopplane/host/config.py` | + `RuntimeConfig.max_subagent_depth: int = 1` (+ coercion + validation) |
| `src/loopplane/host/assembly.py` | register the adapter when cap ≥ 1; child-host closure; pass depth to controller |
| `src/loopplane/controller/controller.py` | + `subagent_depth` kwarg; `drive()` sets it on `RunContext` |

The agent loop, the orchestration core, the gateway pipeline, the event schema, and the content model are
**unchanged**.
