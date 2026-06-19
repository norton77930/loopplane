# Implementation Plan: Plan Mode (read-only investigation → human approval → execute)

**Branch**: `038-plan-mode` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/038-plan-mode/spec.md`

## Summary

Add a LoopPlane-native **plan mode**: while a run is in plan mode the agent may only
do **read-only investigation**; the agent proposes a plan, a **human approves**, and
only then the agent **executes**. The mechanism is **additive and enforced only at
the Tool Gateway decide stage** (Constitution V), mirroring the spec-034
`network_policy` precedent:

- A **`plan_mode_policy` decider** (`src/loopplane/governance/plan_mode.py`) that,
  while plan mode is active, **denies** any tool with `ToolDescriptor.read_only ==
  False` **except** an allowlist (`ask_user`, `exit_plan_mode`), and **allows** every
  read-only tool; a **no-op allow** when inactive. It reads plan-mode activity from a
  per-run holder on the `RunContext` it is given, and is composed through the
  **existing** combinators (`all_of` deny-wins + `safe_failure` fail-closed) in
  `host/assembly.py::_build_decider` — **no new gateway stage**.
- A minimal per-run holder **`PlanModeState(active: bool)`** in
  `src/loopplane/context.py`, carried on an additive **`RunContext.plan_mode:
  PlanModeState | None = None`** field. The decider **reads** it; the
  `exit_plan_mode` tool **flips** it. Both receive the **same** per-run `RunContext`
  instance (verified: the Gateway calls `decide(call, descriptor, context, emitter)`
  and `adapter.invoke(name, input, context)` with the one context built in
  `controller.drive()`), so the holder is the single, additive sharing channel — no
  process-global state.
- An **`exit_plan_mode` tool** on the Internal Tool Adapter
  (`src/loopplane/tools/internal.py`): input `plan` (text); it submits the plan for a
  human decision **reusing the existing human round-trip** (`context.interactions`,
  the same `InteractionBroker.ask_question` that `ask_user` uses). On **approve** →
  set the holder inactive and return a success result; on **reject / no human** →
  leave plan mode active and return a clear normalized outcome. The tool is
  **allowlisted** and marked **not** `read_only`.
- An additive, default-off **`RuntimeConfig.plan_mode: bool = False`** flag (also
  coerced in `from_mapping`), wired through `host/assembly.py` into the
  `RuntimeController` (one additive constructor kwarg) so a run starts with an active
  `PlanModeState`; default leaves existing runs **byte-identical**.

The change is purely additive: **no core agent-loop change**, **no gateway-pipeline
change**, **no event-bus / event-schema change**, and **no existing-tool / descriptor
behavior change**. **No ADR** (a decide-stage policy, not a boundary or schema
change). This is the **first Tier-2 unit** (agentic workflow depth).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Standard library + the existing `loopplane` internals only
(`governance` combinators, the `RunContext`, the `InteractionBroker`,
`ToolDescriptor`). No new runtime dependency. `anyio`/`pydantic` are already in core.

**Storage**: N/A — `PlanModeState` is an in-memory per-run holder on `RunContext`;
nothing is persisted.

**Testing**: pytest (offline, deterministic), mirroring `tests/governance_helpers.py`
(`call`/`descriptor`/`decide`, extended with a context-bearing runner) and the
internal-tool harness in `tests/unit/test_internal_file_tools.py` (the
`_context`/`_invoke` pattern, `pytest.mark.anyio`), plus a scripted `InteractionBroker`
for the approve/reject/no-human round-trip. No network, no real model.

**Target Platform**: Cross-platform library runtime (Windows/macOS/Linux)

**Project Type**: Single project — embeddable Python library/runtime

**Performance Goals**: Interactive single-call latency; the decider is a constant-time
descriptor/flag check; no new per-call work on the non-plan-mode path (absent holder →
immediate allow).

**Constraints**: Enforcement at the Gateway decide stage only (V); no new gateway
stage; no core agent-loop change; no event-schema change; default-off so existing runs
are byte-identical; the per-run holder must not be process-global.

**Scale/Scope**: One new tiny governance module (`plan_mode_policy`), one new holder
+ one additive `RunContext` field, one new internal tool (descriptor + handler) reusing
the existing broker, one additive `RuntimeConfig` flag, one additive
`RuntimeController` kwarg + one line in `drive()`, the `_build_decider` composition,
plus deterministic offline unit tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Spec-First**: PASS. Plan traces to spec 038; tasks will trace to this plan.
- **II — Greenfield**: PASS. New code written fresh; no legacy code copied; the
  reference harnesses inform the *concept* only (IX), re-derived as a decide-stage policy.
- **III — Harness Before Loop Automation**: PASS. No scheduler/validator/evaluator/
  auto-iteration. Plan mode is a **governance policy + one tool**, not loop automation:
  the human is the approver and the existing loop drives the turns unchanged. It opens
  the Tier-2 (agentic workflow) line without implementing any automated loop engine.
- **IV — Runtime Boundary Clarity** (key gate): PASS. No boundary is blurred. The
  policy is a decide-stage `PolicyDecider` (the Tool Gateway's existing seam); the
  `exit_plan_mode` tool lives behind the Internal Tool Adapter SPI; the human round-trip
  is the **existing** `InteractionBroker` (Human Approval boundary), reused verbatim. The
  per-run holder rides the **existing** `RunContext` that the Gateway already hands to
  both the decider and the tool — no reach-through, no new cross-component channel. → **No
  ADR required.**
- **V — Tool Gateway Ownership** (key gate): PASS. All enforcement is at the Gateway
  **decide stage**; plan mode is a *policy*, never a bypass. `exit_plan_mode` is resolved,
  authorized, and executed **only** through the Gateway (it is allowlisted by the policy so
  it survives its own gate), and returns its outcome as the gateway output union
  (`TextBlock` / `ErrorOutput`) — no raw exception crosses the boundary. The policy never
  resolves or executes a tool; it only returns allow/deny. No new gateway stage.
- **VI — Event Bus**: PASS. **No event-schema change.** `exit_plan_mode` reuses the
  existing `ask_question` round-trip, which emits the existing `question-asked` /
  `question-answered` events; no new event type, no `SCHEMA_VERSION` bump. The loop emits
  the same normalized events as today.
- **VII — Public-Safe**: PASS. No secret, no internal path. `RuntimeConfig.plan_mode` is a
  bare boolean (no credential). The submitted plan is agent/human content carried through
  the existing question round-trip; no new persistence.
- **VIII / IX — No SDK Replacement / Reference-not-clone**: PASS. No framework adopted.
  Plan mode is re-derived as a LoopPlane decide-stage policy + one internal tool, not a
  copy of a reference harness's implementation.
- **X — Testable Evolution**: PASS. Deterministic offline tests for the policy (active
  deny/allow + allowlist + inactive no-op + fail-closed), the tool (approve clears /
  reject + no-human keep, via a scripted broker), and the assembly wiring + an
  off-equals-no-policy proof. Rollback = delete the policy, the holder + `RunContext`
  field, the tool, the config flag, the controller kwarg, and the `_build_decider`
  composition (all additive, reversible).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/038-plan-mode/
├── plan.md              # This file
├── research.md          # Phase 0 output (seam findings + the state-sharing choice)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── plan-mode.md     # Policy + tool + holder + config contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/loopplane/
├── governance/
│   ├── plan_mode.py        # NEW: plan_mode_policy(state, *, allowlist) — deny non-
│   │                       #   read-only while active, allowlist + read-only allowed;
│   │                       #   no-op when inactive/absent. Reads the per-run holder.
│   └── __init__.py         # MODIFY: export plan_mode_policy (additive __all__)
├── context.py              # MODIFY: + PlanModeState(active: bool) holder;
│                           #   + RunContext.plan_mode: PlanModeState | None = None
├── tools/
│   └── internal.py         # MODIFY: + exit_plan_mode descriptor (network=False,
│                           #   read_only=False) + _exit_plan_mode handler reusing
│                           #   context.interactions (the ask_user round-trip)
├── host/
│   ├── config.py           # MODIFY: RuntimeConfig + plan_mode: bool = False
│   │                       #   (+ from_mapping coercion); no secret
│   └── assembly.py         # MODIFY: _build_decider composes plan_mode_policy via the
│   │                       #   existing all_of + safe_failure; pass plan_mode to the
│   │                       #   RuntimeController
├── controller/
│   └── controller.py       # MODIFY (minimal, additive): + plan_mode constructor kwarg;
│                           #   drive() builds RunContext(plan_mode=PlanModeState(
│                           #   active=True)) when enabled. ONLY per-run wiring — the
│                           #   loop/turn cycle is untouched.
├── model/
│   └── boundary.py         # USE (unchanged): ToolDescriptor.read_only
├── approval/
│   └── interactions.py     # USE (unchanged): InteractionBroker.ask_question
└── gateway/                # USE (unchanged): decide stage already passes (context)

docs/
├── api-reference.md        # MODIFY: + plan_mode_policy bullet under loopplane.governance
└── loopplane-agent-board.md# MODIFY: + 038 §3 row; §4 update (038 done, opens Tier-2)

tests/
├── governance_helpers.py   # MODIFY (additive): a context-bearing decide runner
│                           #   (decide_with_context) so a policy that reads RunContext
│                           #   can be exercised; existing `decide` unchanged.
└── unit/
    ├── test_plan_mode_policy.py   # NEW: active deny non-read-only / allow read-only +
    │                              #   allowlist / inactive no-op / fail-closed / deny-wins
    ├── test_plan_mode_tool.py     # NEW: exit_plan_mode approve clears + reject keeps +
    │                              #   no-reviewer keeps; outcome shapes; subsequent
    │                              #   write_file decision flips with the holder
    └── (tests/contract/test_host_config.py)  # MODIFY (additive): plan_mode wiring →
                                    #   decider denies write_file when active; from_mapping
```

**Structure Decision**: Single-project library layout. The policy is a new tiny
`governance/plan_mode.py` (cohesive with `network.py`), composed through the **existing**
`_build_decider` combinators. The holder rides the **existing** per-run `RunContext`
(the one object both the decider and the tool already receive) — chosen over a closure
shared at construction because the decider/adapter are built once and shared across all
runs/sessions, so only `RunContext` is genuinely per-run (see research Decision 2). The
tool is a local extension of `InternalToolAdapter` reusing the existing broker. The only
unavoidable per-run wiring is in `controller.drive()` (the single place `RunContext` is
constructed) — kept to one additive kwarg + one line; the loop/turn cycle is untouched.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
