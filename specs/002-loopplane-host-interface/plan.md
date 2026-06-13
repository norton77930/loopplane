# Implementation Plan: Host Integration Interface

**Branch**: `002-loopplane-host-interface` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-loopplane-host-interface/spec.md`

## Summary

Build a thin **host-integration layer** over the completed Phase-1 runtime foundation so an external
application can embed and run LoopPlane from one configured entry point — without hand-wiring the
Runtime Controller, Tool Gateway, stores, approval, and event sink, and without re-implementing any
Phase-1 internal. The deliverable is a new `loopplane.host` package containing three pieces plus an
example and docs:

1. a declarative, programmatic **`RuntimeConfig`** that selects model provider, tools, optional
   memory/checkpoint/artifact backends, and approval behavior (FR-010–FR-015);
2. a **Reference Runner** (`assemble`) that maps a `RuntimeConfig` onto wired Phase-1 components and
   drives runs with the scripted model and internal tools (FR-020–FR-024);
3. a **`LoopPlaneHost`** facade — the Host Application Interface — that validates the config fail-fast,
   starts runs, exposes the normalized event stream, and offers the interactive round-trip
   (FR-001–FR-008);

plus a minimal example runner (FR-030–FR-033), an embedding guide (FR-050–FR-053), and an end-to-end
smoke suite (FR-040–FR-043). Per the requester's two decisions: the configuration is a **programmatic
object** (also constructible from a plain mapping), **no file-based configuration loading** is in
scope this phase, and the Reference Runner consumes that object directly. This `/speckit-plan` run
produces **`plan.md` only**; `research.md`, `data-model.md`, `contracts/`, and `tasks.md` are out of
scope for this command (design detail is folded into the sections below).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phase 1).

**Primary Dependencies**: The Phase-1 `loopplane` runtime itself (its public surface). No new runtime
dependency is introduced — the host layer is pure assembly over `anyio` / `pydantic` v2 already in the
core. Optional extras (`loopplane[mcp]`, `loopplane[otel]`) are reused unchanged when a configuration
selects external tools or observability.

**Storage**: Reuses Phase-1 filesystem stores (`CheckpointStore`, `ArtifactStore`, `MemoryStore`)
under a host-chosen base directory; no new storage mechanism and no database.

**Testing**: pytest + the anyio plugin (Phase-1 toolchain). New suites: a host-config contract suite
(`tests/contract/`), an end-to-end smoke suite and a gating-equality suite (`tests/integration/`). The
scripted model substitute (`ScriptedModel`) remains the primary deterministic instrument.

**Target Platform**: Cross-platform library (Windows, Linux, macOS) embedded in a host process; the
host layer adds no host, transport, or UI dependency (NFR-005, FR-008).

**Project Type**: Single library — one new sub-package (`loopplane.host`) added to the existing
src-layout package, keeping the "one package per component boundary" convention from Phase 1.

**Performance Goals**: Negligible overhead over the bare runtime; assembly happens once per host
instance; the event path adds only a thin guard wrapper. Determinism preserved (NFR-002).

**Constraints**: Zero-behavior-change overlay when optionals are off (NFR-003); public-safe with no
secrets in any configuration object (NFR-004); deterministic event ordering inherited from Phase 1
(NFR-002); host/transport/UI-free (NFR-005); minimal surface, no speculative product features
(NFR-006).

**Scale/Scope**: Single process; one configured host driving sequential, independent runs/sessions
(NFR-008 from Phase 1 carries over). One new package (~4 modules), one example, one doc, three test
suites. No change to Phase-1 source.

## Dependency on Phase 1 (`001-loopplane-runtime-foundation`)

Phase 2 is **strictly additive** over the merged Phase-1 foundation and consumes only its declared
public surface — it imports Phase-1 components and composes them; it does not modify or re-implement
them (NFR-001, FR-060). The exact Phase-1 surface this layer builds on:

| Phase-1 surface (public) | How the host layer uses it |
|---|---|
| `loopplane.controller.RuntimeController` (`create_session`, `drive`, `attach`, `detach`, `resume`, `terminate`, `list`, `history_snapshot`) | The assembled object the facade owns and delegates lifecycle to (FR-003, FR-006) |
| `loopplane.controller.Dispatcher` (abstract channels: submit-input, cancel, approval-decision, question-answer; pending-interaction registry; disconnect semantics) | Backs the interactive session round-trip the facade exposes (US3) |
| `loopplane.gateway.ToolGateway` (`register`, `register_adapter`, `artifact_handoff=`, `decide=`) | The chokepoint into which the runner registers configured tools/adapters; never bypassed (FR-022, Constitution V) |
| `loopplane.model` (`ModelBoundary`, `ScriptedModel`, content blocks) | The model seam the config selects; `ScriptedModel` is the credential-free default (FR-021) |
| `loopplane.approval.HumanApproval` (allow/deny/ask rules, `skill_profiles=`) | Built from the config's approval policy; enforcement stays in Phase 1 (FR-014) |
| `loopplane.checkpoint.CheckpointStore` / `loopplane.artifacts.ArtifactStore` + `make_artifact_handoff` | Constructed from `StorageConfig` and wired together automatically (FR-002) |
| `loopplane.memory.MemoryStore`; `loopplane.skills` (`load_skills`, `skill_profiles`, `SkillToolAdapter`) | Constructed from optional config; off by default (FR-012) |
| `loopplane.events.RuntimeEvent` + the normalized, versioned vocabulary | Forwarded verbatim to the host sink; unknown types tolerated downstream (FR-004, Constitution VI) |
| `loopplane.observability.maybe_attach(sink)` | Optionally wraps the sink when `observability=True`; off by default (FR-012) |

**Non-duplication guarantee (FR-060–FR-062, SC-008)**: the host layer contains *no* Agent Loop,
dispatcher mechanics, gateway pipeline, event vocabulary, or store internals. Any capability Phase 2
needs that Phase 1 lacks (config validation, sink-failure isolation, the facade itself) is added
*above* the Phase-1 boundaries, never by editing Phase-1 modules.

## Architecture Boundaries

Component ownership is normative in [spec.md → Host Interface Boundaries](./spec.md#host-interface-boundaries).
The dependency direction is strictly inward: the host layer depends on the Phase-1 core; the core has
zero knowledge of the host layer.

```text
host application
      │  builds
      ▼
RuntimeConfig ──► LoopPlaneHost (facade) ──► assemble() [Reference Runner]
                       │                            │ wires (no bypass)
                       │ delegates                  ▼
                       ▼                    RuntimeController ──► Agent Loop ──► Model boundary
                 host event sink ◄── guard ◄── Runtime Event Bus      │
                 host approval handler ◄──────── Human Approval ◄── Tool Gateway ──► adapters
                                                                          │
                                              Checkpoint / Artifact / Memory (Phase-1 stores)
```

Allowed interactions (everything else is prohibited reach-through):

- `LoopPlaneHost` calls **only** the Phase-1 public surface in the table above; it never touches Agent
  Loop, Dispatcher, or store internals.
- The Reference Runner (`assemble`) is the **only** place that constructs and wires Phase-1
  components; the facade and the example both go through it (FR-024) — there is no second wiring path.
- Tools reach execution **only** by being registered into the `ToolGateway` (Constitution V); the host
  layer offers no alternate execution path.
- The host sink consumes the **normalized** event stream and adapts on its own side (Constitution VI);
  the guard wrapper isolates sink failures without reordering events (FR-007).

## Host Application Interface — API Shape

The public surface lives in `loopplane.host` and is intentionally small. Sketch below is **design
intent for the implementation phase, not code delivered by this step**.

```python
from loopplane.host import (
    RuntimeConfig, ToolSpec, ApprovalPolicy, StorageConfig, MemoryConfig, SkillsConfig,
    LoopPlaneHost, build_host, RunOutcome, ConfigError,
)

host = LoopPlaneHost(config)            # assemble + validate; raises ConfigError fail-fast (FR-005)
# build_host(config) is an equivalent factory alias (the Reference Runner entry point).

# One-shot run (US1):
outcome: RunOutcome = await host.run(
    [TextBlock(text="please echo hello")],
    on_event=my_sink,                   # async (RuntimeEvent) -> None  (FR-004)
    on_approval=my_handler,             # optional; required only if the policy has 'ask' tools (FR-014)
)
# outcome.session_id, outcome.termination_reason, outcome.history

# Interactive round-trip (US3) — thin wrapper over the Phase-1 Dispatcher:
async with host.session(on_event=my_sink, on_approval=my_handler) as session:
    await session.submit([TextBlock(text="...")])
    await session.answer_approval(request_id, allow=True, scope="session")
    await session.answer_question(request_id, answers)
    await session.cancel()

# Durable lifecycle reuse (US1/US2) — delegated to the controller:
host.list_sessions()
await host.resume(session_id)
await host.attach(session_id, on_event=my_sink)   # replays history as events (replay: true)
```

Shape decisions:

- **`LoopPlaneHost(config)`** owns one assembled `RuntimeController` plus the wired gateway/stores. It
  is reusable for multiple **sequential** runs/sessions with no cross-run state leakage (FR-006); each
  `run`/`session` creates a fresh Phase-1 session.
- **`RunOutcome`** is the only thing returned for a one-shot run: `session_id: str`,
  `termination_reason: str`, `history: tuple[HistoryEntry, ...]` (a Phase-1 history snapshot). The host
  never reaches into Agent Loop internals to learn the outcome (FR-003).
- **`host.run`** = `create_session` → `drive` with a guarded sink; **`host.session`** binds a
  Dispatcher channel pair and exposes its inbound request vocabulary (submit-input, cancel,
  approval-decision, question-answer) one-to-one (FR-001 reuse, US3).
- **`ConfigError`** carries a field-level, public-safe message and is raised before any session is
  created (FR-005); no secret or private path ever appears in it (FR-013).
- The facade has **no** web/desktop/CLI/transport dependency and is import-safe from a plain process
  (FR-008).

## Reference Runner Design

The Reference Runner is the assembly function `assemble(config) -> AssembledRuntime` in
`loopplane/host/assembly.py`. `LoopPlaneHost.__init__` calls it, and so does the example runner —
they share the **one** wiring path (FR-024), so smoke tests exercise the real embedding path.

`assemble` performs, in order:

1. **Validate** the config (FR-005, FR-010–FR-015): model present; tool names unique across
   `tools`/`tool_adapters`; selected optional capabilities importable (e.g. `[mcp]`/`[otel]`); approval
   tool names reference known tools. On failure → `ConfigError`, no components built.
2. **Resolve the model** seam: use `config.model` directly (a `ModelBoundary`, e.g. `ScriptedModel` —
   FR-021); credentials, if any, already live inside that object (out of band, FR-013).
3. **Build the gateway**: `ToolGateway(artifact_handoff=make_artifact_handoff(artifact_store))` when a
   `StorageConfig` is present, else a plain `ToolGateway`; then `register(descriptor, handler)` each
   `ToolSpec` and `register_adapter(...)` each adapter (FR-022). At least one test tool (an echo-style
   tool) is available so a tool-calling run is demonstrable end-to-end.
4. **Build approval**: translate `ApprovalPolicy` (allow/deny/ask sets) into Phase-1 `HumanApproval`
   permission rules; add `skill_profiles(skills)` when skills are configured; pass as `decide=` to the
   gateway. Absent policy → gateway default allow-all (test posture) (FR-014).
5. **Build durability**: from `StorageConfig.root`, construct `CheckpointStore` and `ArtifactStore`
   under that base; both, or neither, plus consistent artifact handoff — the host never asks the
   application to connect `make_artifact_handoff` by hand (FR-002, edge case).
6. **Build optionals** (all default-off, FR-012): `MemoryStore` from `MemoryConfig`; `load_skills(...)`
   + `SkillToolAdapter` from `SkillsConfig`; observability deferred to sink-wrap time.
7. **Assemble** `RuntimeController(model, gateway, event_sink=<bound at run time>, checkpoint_store,
   artifact_store, memory_store, skills)` and return it with the handles the facade needs.

Properties: deterministic given identical scripted behavior and tool outcomes (FR-023, inherited from
Phase-1 NFR-001); pure composition — no Phase-1 internal is re-implemented (FR-060).

## Runtime Configuration Model

A frozen, declarative dataclass tree, **constructible in code and from a plain mapping** (FR-010,
FR-011). Object-typed collaborators (the model, tool handlers, adapters) are passed as objects; scalar
and structured selections (storage root, thresholds, approval sets, flags) may come from a mapping.
**No configuration-file format and no on-disk loading are in scope this phase** (requester decision) —
`from_mapping` accepts an already-parsed `Mapping`, nothing more.

```python
@dataclass(frozen=True)
class RuntimeConfig:
    model: ModelBoundary                               # required (FR-005 if missing)
    tools: tuple[ToolSpec, ...] = ()                   # (descriptor, handler) → gateway.register
    tool_adapters: tuple[object, ...] = ()             # e.g. MCP adapter / SkillToolAdapter
    approval: ApprovalPolicy | None = None             # None → allow-all (test posture)
    storage: StorageConfig | None = None               # None → ephemeral (no checkpoint/artifact)
    memory: MemoryConfig | None = None                 # None → off
    skills: SkillsConfig | None = None                 # None → off
    observability: bool = False                        # default off (FR-012)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RuntimeConfig": ...

@dataclass(frozen=True)
class ToolSpec:
    descriptor: ToolDescriptor
    handler: ToolHandler                               # async (call_input, context) -> blocks

@dataclass(frozen=True)
class ApprovalPolicy:                                  # minimal allow/deny/ask per tool (FR-014)
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    ask:  frozenset[str] = frozenset()

@dataclass(frozen=True)
class StorageConfig:
    root: Path                                         # host-chosen base dir (host-overridable, A10)
    artifact_threshold: int | None = None              # passthrough to Phase-1 defaults
    artifact_budget: int | None = None

@dataclass(frozen=True)
class MemoryConfig:  source: Path                      # directory of memory entries
@dataclass(frozen=True)
class SkillsConfig:  sources: tuple[Path, ...]         # directories of skill packages
```

Public-safety rules (FR-013, NFR-004, SC-006): the config **carries no secrets, credentials, provider
keys, or private paths**. Any credential lives inside the host-supplied `model` object or the host's
environment. `StorageConfig.root` is a runtime host location chosen by the application; committed
examples and docs use relative, non-private paths (e.g. `./loopplane-data`). The live approval handler
is supplied at `run`/`session` time, not stored in the config.

## Event Consumption Model

The host consumes the **normalized** Phase-1 event stream; the host layer adds only thin, consumer-side
adaptation (Constitution VI, FR-004).

- **Sink shape**: `on_event` is the Phase-1 `event_sink` signature — `async (RuntimeEvent) -> None`.
  The host forwards every event in deterministic order; it never filters or reorders (NFR-002).
- **Observability wrap**: when `config.observability` is true, the host wraps the sink via
  `observability.maybe_attach(sink)` (metadata-only, off by default) — otherwise the sink is used as
  is, guaranteeing zero behavior change (FR-012, SC-003).
- **Failure isolation (FR-007)**: the host wraps the sink in a guard that catches an exception raised
  by a misbehaving consumer, surfaces it as a `diagnostic`-class signal, and continues delivering
  ordered events to the run — session state and ordering for well-behaved consumers are never
  corrupted. This guard is the host layer's, not the loop's.
- **Unknown/future event types**: forwarded unchanged; consumers skip what they do not recognize, per
  Phase-1 tolerance (FR-004) — the host neither drops nor rewrites them.
- **Interactive stream (US3)**: in `host.session(...)`, events flow over the Dispatcher outbound
  channel to the same sink, while the inbound vocabulary (submit-input, cancel, approval-decision,
  question-answer) is exposed as `session.submit/cancel/answer_approval/answer_question`, matching the
  Phase-1 run-lifecycle contract. Cancellation ends the run with a `cancelled` terminal event without
  raising (US3 scenario 3).

## End-to-End Smoke Test Strategy

The smoke suite proves the full path through the **public** interface and reuses Phase-1 guarantees
rather than re-testing internals (FR-040–FR-043). Each test maps to a Success Criterion.

| Test (location) | Asserts | SC |
|---|---|---|
| `integration/test_host_smoke.py::text_only` | request → `LoopPlaneHost.run` → scripted text → ordered events → one terminal event | SC-001, SC-004 |
| `…::tool_call` | scripted tool-call → `ToolGateway` executes the echo test tool → `tool-call-*` events between turns | SC-004 |
| `…::determinism` | same scenario run twice → identical event sequence + identical `RunOutcome` | SC-002 |
| `…::checkpoint` | with `StorageConfig` → durable records appended for the run are inspectable | SC-004 |
| `…::artifact_offload` | an oversized test-tool result is offloaded and retrievable by reference | SC-004 |
| `…::sequential_runs` | one host drives two runs; no state leaks; both deterministic | SC-001 |
| `…::cancel_midrun` | cancel through the round-trip → `cancelled` terminal, no raise | SC-002 |
| `…::consumer_failure` | a sink that raises is isolated as a diagnostic; ordering intact | (FR-007) |
| `contract/test_host_config.py::invalid` | missing model / duplicate tool names / unavailable capability → `ConfigError` before any run | SC-005 |
| `contract/test_host_config.py::from_mapping` | a plain mapping yields an equivalent config | (FR-011) |
| `integration/test_host_gating.py::equality` | all optionals off → event sequence identical to a bare `RuntimeController` run | SC-003 |

**Final test-file split** (as implemented in [tasks.md](./tasks.md)): US1 happy-path →
`test_host_smoke.py`; US2 config + gating → `test_host_config.py` + `test_host_gating.py`; US3
events/round-trip → `test_host_session.py`; US4 determinism/durability → `test_host_durability.py`;
plus the Phase-1 import guard `test_host_imports.py`. The table above groups cases logically.

The minimal example runner (below) is itself a smoke target: running it produces a fixed transcript the
suite can assert on (FR-030, FR-032). Public-safety scanning of committed Phase-2 files reuses the
Phase-1 scan test and extends its file set (SC-006).

## Public-Safe Examples & Documentation Strategy

- **`examples/host_quickstart.py`** (FR-051, FR-030–FR-033): a runnable embedding example and the
  minimal developer runner in one file. It builds a `RuntimeConfig` (scripted model + one echo tool),
  constructs `LoopPlaneHost`, runs a fixed scenario, and prints the ordered event stream and outcome.
  It optionally accepts a single scenario name (`text` | `tool` | `durable`) and prints a clear,
  public-safe message on an unknown argument (FR-033) — it deliberately stops there and does **not**
  become a product CLI (FR-031). Credential-free, no network (FR-032).
- **`docs/embedding-host.md`** (FR-050, FR-053): a public-safe guide — config → `LoopPlaneHost` →
  event consumption → durable + approval variants — that *points to* the Phase-1 boundaries
  (`docs/quickstart.md`, the spec's boundary table) rather than restating runtime internals. A short
  "Host interface vs. raw runtime" note explains that Phase 2 is an integration layer over Phase 1.
- **Public-safety (FR-052, NFR-004, SC-006)**: no raw private reference material, private project or
  repository names, internal paths, network addresses, or secrets; examples use relative paths and the
  scripted model. The private reference directory is never read, modified, or committed.

## Project Structure

### Documentation (this feature)

```text
specs/002-loopplane-host-interface/
├── spec.md                 # Feature specification (complete)
├── plan.md                 # This file (/speckit-plan output — the only artifact this run)
├── checklists/
│   └── requirements.md      # Spec quality checklist (complete)
└── tasks.md                 # Deferred to /speckit-tasks (NOT created here)
```

`research.md`, `data-model.md`, and `contracts/` are intentionally **not** generated: the requester
scoped this run to `plan.md` only, and the configuration/API/event design that would populate them is
folded into the sections above.

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/host/
├── __init__.py        # public exports: RuntimeConfig, ToolSpec, ApprovalPolicy, StorageConfig,
│                      #   MemoryConfig, SkillsConfig, LoopPlaneHost, build_host, RunOutcome, ConfigError
├── config.py          # RuntimeConfig + sub-configs + from_mapping + validation (FR-010–FR-015)
├── assembly.py        # Reference Runner: assemble(config) → wired Phase-1 components (FR-020–FR-024)
└── host.py            # LoopPlaneHost facade, RunOutcome, guarded sink, session round-trip (FR-001–FR-008)

examples/
└── host_quickstart.py # runnable embedding example + minimal smoke runner (FR-030–FR-033, FR-051)

docs/
└── embedding-host.md  # public-safe embedding guide (FR-050, FR-053)

tests/
├── contract/
│   ├── test_host_imports.py    # Phase-1 public-surface import guard; no web/transport/UI import (NFR-001; FR-008)
│   └── test_host_config.py     # config validation, from_mapping, fail-fast, no-secret-field (SC-005; FR-005/011/013)
└── integration/
    ├── test_host_smoke.py      # US1 happy path: text + tool-call run, sequential runs (SC-001/004)
    ├── test_host_session.py    # US3: event order, cancel, approval round-trip, consumer-failure (FR-004/007/014)
    ├── test_host_durability.py # US4: determinism, checkpoint, artifact offload/retrieve (SC-002/004; FR-042)
    └── test_host_gating.py     # gating-equality vs bare controller (SC-003; FR-043)
```

**Structure Decision**: one new sub-package `loopplane.host`, mirroring Phase 1's one-package-per-
boundary convention, so the host layer is a single, clearly-bounded, independently-revertible addition.
No Phase-1 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks
are deferred to [`/speckit-tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| HA — Config contract | `config.py`: `RuntimeConfig` + sub-configs + `from_mapping` + validation | `test_host_config.py` green; invalid configs fail fast (SC-005) | Revert package; nothing depends on it yet |
| HB — Reference Runner | `assembly.py`: `assemble(config)` wiring all Phase-1 components, scripted model + echo test tool | text + tool-call runs drive end-to-end through the assembly | Revert to config-only |
| HC — Host facade | `host.py`: `LoopPlaneHost`, `RunOutcome`, guarded sink, `session` round-trip; `__init__` exports | `test_host_smoke.py` green incl. determinism, checkpoint, artifact, cancel, sequential, consumer-failure | Revert facade; runner unaffected |
| HD — Gating + examples + docs | `test_host_gating.py`; `examples/host_quickstart.py`; `docs/embedding-host.md`; extend public-safety scan | gating equality (SC-003); example reproduces documented output (SC-007); scan clean (SC-006) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Configuration surface creeps toward a product config language | Keep `RuntimeConfig` to minimal selectors (NFR-006); no file format/loading this phase; Constitution III is a review gate; any new need becomes a future-phase spec (FR-061) |
| The integration layer accidentally changes Phase-1 behavior | Gating-equality test vs a bare `RuntimeController` (SC-003, FR-043) plus the repeat-run determinism test (SC-002) catch any divergence |
| The facade and the example drift into two different wirings | A single assembly path: both go through `assemble()` (FR-024); a smoke test drives the example’s exact path |
| A misbehaving host event consumer corrupts a run | The guard wrapper isolates sink exceptions as diagnostics; a dedicated `consumer_failure` test asserts ordering survives (FR-007) |
| A secret or private path leaks through a configuration object | Config carries no secrets by contract (FR-013); credentials stay in the host-supplied model object/environment; public-safety scan over committed Phase-2 files (SC-006) |
| A selected optional extra (`[mcp]`/`[otel]`) is missing and surfaces a raw traceback | `assemble()` checks capability availability and fails fast with a public-safe `ConfigError`, never a raw import error (FR-005, edge case) |
| Phase-1 public surface evolves and breaks the host layer | The layer pins to the documented Phase-1 public surface only; contract + integration tests fail loudly if that surface changes, signalling a coordinated update |

**Rollback posture**: the `loopplane.host` package is purely **additive** over Phase 1 — small,
task-scoped commits on this feature branch, each phase (HA–HD) independently revertible. Reverting any
or all of them leaves the Phase-1 runtime and its on-disk records untouched (the host layer introduces
no new storage format and reuses Phase-1 stores). All optional subsystems remain default-off, so a
partial revert can never change core-loop behavior.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before design; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit-tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.host` package written fresh; composes Phase-1 public API only; no legacy code copied |
| III | Agent Harness Before Loop Automation | PASS | Host-integration layer only; the entire out-of-scope list (scheduler/validator/evaluator/auto-iteration/…) is excluded (FR-061); minimal surface (NFR-006) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package with a single responsibility; depends inward on Phase 1; spec boundary table assigns ownership; no Phase-1 boundary blurred (FR-060–FR-062) |
| V | Tool Gateway Ownership | PASS | The runner registers tools **into** `ToolGateway` and adds no bypass path; all tools still execute through the gateway (FR-022) |
| VI | Runtime Event Bus Ownership | PASS | Host consumes normalized events and adapts on the consumer side; the guard isolates sink failures without new event types or reordering (FR-004, FR-007) |
| VII | Public-Safe Documentation | PASS | No secrets in any config (FR-013); examples/docs public-safe (FR-052); the private reference stays untracked; scan extended (SC-006) |
| VIII | No SDK Replacement | PASS | No agent framework introduced; pure assembly over LoopPlane's own runtime |
| IX | Reference, Not Clone | PASS | Design re-derived from the Phase-1 public surface and the spec; no external host cloned |
| X | Testable Evolution | PASS | Each phase has required tests, a validation gate, and a rollback note; the package is additive and revertible; optionals default-off |

**Post-design re-check**: PASS — the API shape, configuration model, and event model introduce no
boundary violation and no Phase-1 modification. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
