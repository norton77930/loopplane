# Implementation Plan: Dynamic Subagents (model-driven one-shot spawning)

**Branch**: `043-dynamic-subagents` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/043-dynamic-subagents/spec.md`

## Summary

Add the **model-driven one-shot subagent** primitive both reference harnesses expose (claude-code's
`Agent`, orion's `SubAgentCreate`): a `spawn_subagent` **Tool-Gateway tool** that runs **one** bounded
child agent through the **existing** Phase-3 entry point (`loopplane.engineering.run_loop`) and returns
the child's final assistant text to the parent. The mechanism is **additive, reuse-first, and SAFE**
under a **hard recursion-depth cap**:

- A new **`SpawnSubagentAdapter`** (`src/loopplane/tools/subagent.py`, a `ToolAdapter` next to the
  Internal and Web adapters) exposing one tool, `spawn_subagent` (input: a required `task` string + an
  optional `allowed_tools` list). On invoke it builds a **one-shot `LoopDefinition`** — mirroring
  `tests/orchestration_helpers.py`: `ManualTrigger`, `StaticInput(task)`, a `HostRuntimeProfile`
  selector that builds a depth-incremented **child host**, an always-pass `ValidationPolicy`,
  `stop_on_pass()` + `max_iterations=1`, `ObservationPolicy(emit_loop_events=True)` — and drives it
  through the **existing public `run_loop`** (the same entry unit-013's `Coordinator._run_subagent`
  composes). It passes **no live event sink**, so the child's events stay captured (Constitution VI). It
  recovers the child's **final assistant text** from the child host's `history_snapshot(session_id)` and
  returns it as a `TextBlock`.
- The **recursion guard (non-negotiable, fail-safe)**: an additive **`RunContext.subagent_depth: int =
  0`** and a configurable **`RuntimeConfig.max_subagent_depth: int = 0`** (default **off** — byte-identical
  to today; a host sets it to `1` to enable exactly one level). The adapter is constructed with the cap;
  on invoke it reads the per-run `context.subagent_depth` the Gateway already passes to every tool, and
  **denies** (`ErrorOutput`, **no child run started**) when `subagent_depth >= max_subagent_depth`. A
  child runtime is built at **`subagent_depth = parent + 1`** (threaded through an additive defaulted
  `RuntimeController(subagent_depth=...)` kwarg → the one place `RunContext` is built in
  `controller.drive()`). So subagents cannot nest without bound; a cap of `1` allows exactly one level.
- **Failure containment** mirrors unit 013: `run_loop` is wrapped in try/except; a child that raises,
  terminates non-naturally, pauses, or produces no answer maps to a **normalized** `ErrorOutput` (a
  public-safe marker, never a raw exception) and the parent run continues. The Gateway's existing
  per-call time limit + the one-iteration child loop bound an over-run.
- **Events** reuse unit-013's metadata-only aggregation: the captured child `LoopOutcome.events` are
  surfaced via `loopplane.orchestration.aggregate_events` as a metadata-only count appended to the
  result text; they are **never** re-emitted onto the parent's live bus.
- Wiring is additive in `host/assembly.py`: when `config.max_subagent_depth >= 1`, register a
  `SpawnSubagentAdapter` built with the parent's model, a **child-runtime-config factory** derived from
  the parent `RuntimeConfig` (same model + tools, depth incremented, `allowed_tools` honored), and the
  cap. With `max_subagent_depth = 0` (or a runtime that never opts in) the tool is **not registered** —
  the default-off rollback path.

The change is purely additive: **no core agent-loop change**, **no orchestration-core change**
(`loopplane.orchestration` keeps its strict engineering-only import boundary — the new tool lives in the
`tools` layer, which already imports the gateway/model/context and may import `engineering`), **no
gateway-pipeline change**, **no event-bus / event-schema change**, **no content-model change**, and **no
existing-tool / descriptor behavior change**. **No ADR** (a new Tool-Gateway tool that composes the
existing public loop surface — not a boundary redefinition or a schema change). This is a **Tier-2
autonomy unit**.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Standard library + existing `loopplane` internals only — `loopplane
.engineering` (`run_loop`, `LoopDefinition`, `HostRuntimeProfile`, `StaticInput`, `ManualTrigger`,
`ValidationPolicy`, `ObservationPolicy`, `stop_on_pass`, `max_iterations`, `LoopOutcome`),
`loopplane.orchestration.aggregate_events` (metadata-only event view, reused), the gateway SPI
(`ToolAdapter`, `ErrorOutput`), `RunContext`, `ToolDescriptor`, `TextBlock`, `RuntimeConfig` /
`LoopPlaneHost`. No new runtime dependency. `anyio`/`pydantic` are already in core.

**Storage**: N/A — the child run uses the parent's storage configuration if any (a child host built from
the parent config); `subagent_depth` is an in-memory per-run integer on `RunContext`. Nothing new is
persisted.

**Testing**: pytest (offline, deterministic), mirroring `tests/orchestration_helpers.py` (the one-shot
scripted subagent `LoopDefinition`) and the internal-tool harness in `tests/unit/test_plan_mode_tool.py`
(`_context` / async-generator `invoke` drain, `pytest.mark.anyio`). Both the parent and the child use
`ScriptedModel`. No network, no real model. Covers: the spawn → one-shot child → parent gets the child's
text; the depth cap denies at/over the max with **zero** child runs (a counting child-host factory proves
it); a raising / failing / empty-answer child is contained; a restricted `allowed_tools` child is honored;
the assembly registers the tool only when `max_subagent_depth >= 1`.

**Target Platform**: Cross-platform library runtime (Windows/macOS/Linux)

**Project Type**: Single project — embeddable Python library/runtime

**Performance Goals**: A child is one bounded loop run; the depth check is a constant-time integer
compare; the non-spawning path is unchanged (the tool is absent unless opted in).

**Constraints**: Reuse `run_loop` (no loop rewrite, NFR-001 / IV); enforce at the Gateway (V); no new
gateway stage; no event-schema change (VI); a **hard fail-safe depth cap** (III, NFR-004); default-off so
existing runs are byte-identical; `subagent_depth` must be per-run (never process-global).

**Scale/Scope**: One new tool adapter module (`tools/subagent.py`), one additive `RunContext` field, one
additive `RuntimeConfig` field (+ `from_mapping` coercion + a `validate_config` range check), one additive
`RuntimeController` kwarg + one line in `drive()`, the `host/assembly.py` registration + child-config
factory, the `tools/__init__.py` export, plus deterministic offline tests and the tracking/doc updates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Spec-First**: PASS. Plan traces to spec 043; tasks trace to this plan.
- **II — Greenfield**: PASS. New code written fresh; no legacy code copied; the reference harnesses
  inform the *concept* only (IX), re-derived as a Gateway tool composing the public Phase-3 loop surface.
- **III — Harness Before Loop Automation** (key gate): PASS. This stays a **single bounded one-shot**
  spawn under a **hard depth cap** — opt-in, model-driven, and contained. It introduces **no** autonomous
  multi-agent swarm, no scheduler/auto-iteration engine, no peer messaging, and no background/persistent
  subagents (all explicitly deferred). The child is one Phase-3 loop run that the **existing** layer
  drives unchanged; the cap (`max_subagent_depth`, default 0 = off; a small value like 1 when enabled)
  guarantees boundedness.
- **IV — Runtime Boundary Clarity** (key gate): PASS. No boundary is blurred and the loop is **not**
  rewritten. The child is driven only through the **public** `run_loop` (the documented Phase-3 entry,
  the same one unit-013 composes); the tool lives behind the Internal/Web tool-adapter SPI in the `tools`
  layer (which already imports the gateway, model, and context, and is permitted to import
  `engineering`). The **orchestration core stays pure**: `loopplane.orchestration` keeps its strict
  engineering-only import allow-list (the boundary audit is unchanged) — the spawn tool is *not* added
  there (it would have to import the gateway/context/model, which that package forbids); instead it
  **reuses** orchestration's `aggregate_events` from the allowed direction. The depth field rides the
  **existing** per-run `RunContext` the Gateway already hands to every tool — no reach-through, no new
  cross-component channel. → **No ADR required.**
- **V — Tool Gateway Ownership** (key gate): PASS. `spawn_subagent` is reachable **only** through the
  Tool Gateway and traverses the full pipeline (resolve, validate, decide, execute-under-timeout,
  normalize, size-manage) like any tool — no privileged bypass. The depth cap is enforced **inside the
  tool** at the Gateway boundary (reading the per-run `RunContext`), and every error crossing the
  boundary is the gateway output union (`TextBlock` / `ErrorOutput`) — **no raw exception, secret, or
  private path leaks** (the adapter and the gateway's own `invoke` try/except both normalize). The
  **child's** tools likewise run only through the **child's** Gateway (its own `LoopPlaneHost`); the
  spawn tool resolves/executes no tool itself.
- **VI — Event Bus** (key gate): PASS. **No event-schema change**, no `SCHEMA_VERSION` bump. The child
  run is driven with **no live sink** (exactly as unit-013's coordinator), so its events are **captured**
  in the child `LoopOutcome` and surfaced only as **metadata-only** aggregation (reusing 013's
  `aggregate_events`) — they are never re-emitted, wrapped, or replayed onto the parent's live event bus.
  The parent loop emits the same normalized events as today (a `spawn_subagent` call is an ordinary
  `tool-call-started` / `tool-call-completed` pair).
- **VII — Public-Safe**: PASS. No secret, no internal path. `max_subagent_depth` is a bare integer (no
  credential). Failure markers are fixed public-safe strings (never a raw exception/stack trace). The
  child's model credentials, if any, live in the host-supplied model object reused from the parent
  config, never in this unit.
- **VIII / IX — No SDK Replacement / Reference-not-clone**: PASS. No framework adopted. The primitive is
  re-derived as a LoopPlane Gateway tool that composes the public `run_loop`, not a copy of a reference
  harness's agent implementation.
- **X — Testable Evolution**: PASS. Deterministic offline tests (spawn round-trip, the depth-cap denial
  with zero child runs, failure containment, the restricted toolset, and the assembly gating) with a
  clear rollback: delete the adapter module + the `tools` export, the `RunContext` field, the
  `RuntimeConfig` field + its coercion/validation, the `RuntimeController` kwarg + the `drive()` line, and
  the `assembly.py` registration — all additive and reversible; or simply set `max_subagent_depth = 0`.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/043-dynamic-subagents/
├── plan.md              # This file
├── research.md          # Phase 0: the 013/run_loop seam, the depth-guard design, events handling
├── data-model.md        # Phase 1: the new entities/fields
├── quickstart.md        # Phase 1: how to enable + a spawn example
├── contracts/
│   └── spawn-subagent.md# Tool + depth-guard + failure + events contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/loopplane/
├── context.py              # MODIFY: + RunContext.subagent_depth: int = 0 (additive, default 0)
├── tools/
│   ├── subagent.py         # NEW: SpawnSubagentAdapter (ToolAdapter) — one tool `spawn_subagent`:
│   │                       #   builds a one-shot LoopDefinition over a depth+1 child host and drives it
│   │                       #   via the EXISTING run_loop; depth cap denies at/over max (no child run);
│   │                       #   failure → normalized ErrorOutput; reads final text from the child host's
│   │                       #   history snapshot; child events captured (no live sink) + aggregate_events.
│   └── __init__.py         # MODIFY: export SpawnSubagentAdapter (additive __all__)
├── host/
│   ├── config.py           # MODIFY: RuntimeConfig + max_subagent_depth: int = 1 (+ from_mapping
│   │                       #   coercion; validate_config range check >= 0); no secret
│   └── assembly.py         # MODIFY: when config.max_subagent_depth >= 1, register a SpawnSubagentAdapter
│   │                       #   with the parent model + a child-config factory (parent config, depth+1,
│   │                       #   allowed_tools intersection) + the cap; pass subagent_depth to the controller
├── controller/
│   └── controller.py       # MODIFY (minimal, additive): + subagent_depth constructor kwarg (default 0);
│                           #   drive() builds RunContext(subagent_depth=self._subagent_depth). ONLY
│                           #   per-run wiring — the loop/turn cycle is untouched.
├── engineering/            # USE (unchanged): run_loop / LoopDefinition / HostRuntimeProfile /
│                           #   StaticInput / ManualTrigger / ValidationPolicy / ObservationPolicy /
│                           #   stop_on_pass / max_iterations / LoopOutcome
├── orchestration/          # USE (unchanged, from the allowed direction): aggregate_events (metadata-only)
└── gateway/                # USE (unchanged): the decide/execute pipeline already passes (context) +
                            #   wraps invoke in try/except + a per-call time limit

docs/
├── api-reference.md        # MODIFY: + SpawnSubagentAdapter bullet under loopplane.tools (bijection)
└── loopplane-agent-board.md# MODIFY: + 043 §3 row; §4 update

CHANGELOG.md                # MODIFY: + a **043** entry in ## [Unreleased] ### Added (after 042)
.specify/feature.json       # MODIFY: feature_directory -> specs\043-dynamic-subagents
CLAUDE.md                   # MODIFY: SPECKIT block -> specs/043-dynamic-subagents/plan.md

tests/
├── subagent_helpers.py     # NEW (additive): a deterministic offline harness — build a parent runtime
│                           #   (RuntimeConfig + SpawnSubagentAdapter) over a scripted parent model and a
│                           #   scripted child, with a counting child-host factory to prove zero child
│                           #   runs at the cap; mirrors tests/orchestration_helpers.py.
└── unit/
    └── test_subagent_spawn.py  # NEW: spawn round-trip (parent gets child text); depth cap denies at/over
                            #   max with zero child runs (no unbounded nesting); raising/failing/empty
                            #   child contained; restricted allowed_tools honored; child events not on the
                            #   parent bus; (+ assembly gating: tool absent when max_subagent_depth == 0).
```

**Structure Decision**: Single-project library layout. The spawn tool is a new cohesive adapter in the
`tools` layer (next to `internal.py` / `web.py`), **not** in `loopplane.orchestration` — that package's
import allow-list (enforced by `tests/contract/test_orchestration_boundary.py`) forbids the gateway,
context, and model imports a Gateway tool needs, so adding the tool there would break the boundary. The
tool instead **reuses** the orchestration package from the allowed direction (`aggregate_events`) and
composes the public `run_loop` directly (the same seam the coordinator uses). The child host is built by
an injected child-config factory (constructed in `assembly.py` from the parent `RuntimeConfig`), so the
adapter references `LoopPlaneHost` only under `TYPE_CHECKING` (the controller already uses this pattern)
— no `tools → host` runtime import cycle. The only unavoidable per-run wiring is in `controller.drive()`
(the single place `RunContext` is built) — one additive kwarg + one line; the loop/turn cycle is
untouched.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
