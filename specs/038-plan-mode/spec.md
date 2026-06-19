# Feature Specification: Plan Mode (read-only investigation → human approval → execute)

**Feature Branch**: `038-plan-mode` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "LoopPlane plan mode. While a run is in plan mode the
agent may only do read-only investigation: any non-read-only tool is denied at the
Tool Gateway decide stage, except a small allowlist that must stay usable to make
and submit a plan (`ask_user` and a new `exit_plan_mode` tool); all read-only tools
stay allowed. The agent proposes a plan and submits it via `exit_plan_mode`, which
reuses the existing human round-trip (the interaction broker that `ask_user` uses)
to get a human decision: on approve, plan mode is cleared so subsequent
non-read-only tools are allowed and the agent executes; on reject or no human, the
run stays in plan mode and a clear normalized outcome is returned. Plan mode is
per-run state shared by the decide-stage policy (reads it to deny) and the
`exit_plan_mode` tool (flips it on approval). Entering plan mode is an additive,
default-off `RuntimeConfig.plan_mode` flag. Enforcement is at the Gateway decide
stage only (Constitution V); reuse the existing combinators (deny-wins +
fail-closed) — no new gateway stage, no core agent-loop change, no event-schema
change, no ADR."

## Overview

Both reference harnesses give an agent a **plan mode**: a phase where the agent does
**read-only investigation**, proposes a plan, a **human approves it**, and only then
the agent **executes** with its full tools. LoopPlane has the building blocks — a
single Tool Gateway decide stage (Constitution V), a `ToolDescriptor.read_only`
flag, and a human interaction round-trip (the broker `ask_user` uses) — but no plan
mode that ties them together. This unit adds it, the LoopPlane-native way:
**additive, reuse-first, enforced only at the Gateway decide stage**.

This is the **first Tier-2 unit** (agentic workflow depth): it is the first unit
that shapes the agent's *workflow* (a gated investigate-then-execute phase) rather
than adding a tool or a provider.

The unit adds:

1. A **`plan_mode_policy` decide-stage decider**. While plan mode is active it
   **denies any non-read-only tool**, except a small **allowlist** that must remain
   usable to make and submit a plan — `ask_user` and `exit_plan_mode`. All
   **read-only** tools stay allowed. When plan mode is inactive the policy is a
   **no-op allow**. It is composed through the **existing** decide-stage combinators
   (`all_of` deny-wins + `safe_failure` fail-closed) in the host's decider builder —
   **no new gateway stage** (Constitution V).
2. A minimal **per-run plan-mode state holder** (`PlanModeState(active: bool)`) that
   travels on the per-run `RunContext`. The decider **reads** it (to deny while
   active); the `exit_plan_mode` tool **flips** it (to clear on approval). Both the
   decider and the tool receive the **same** `RunContext` instance for a run, so the
   holder is the single, additive sharing channel — no process-global state, no new
   wiring beyond constructing the holder where `RunContext` is already built.
3. An **`exit_plan_mode` tool** on the Internal Tool Adapter. Its input is the
   proposed `plan` (text). It submits the plan for a human decision **reusing the
   existing human round-trip** (the interaction broker that `ask_user` uses). On
   **approve** → it clears the plan-mode holder (subsequent non-read-only tools are
   then allowed) and returns a result that lets the run proceed to execute. On
   **reject / no human attached** → the run **stays in plan mode** and the tool
   returns a clear normalized outcome. The tool is itself **allowlisted** so it is
   callable while planning, and is marked **not** `read_only` (it mutates run state /
   requests approval).
4. An additive, default-off **`RuntimeConfig.plan_mode` flag** that starts a run in
   plan mode. Leaving it at its default (`False`) leaves every existing run
   **byte-identical** (no policy installed for that reason; existing behavior
   unchanged).

The change is **additive**: the core agent loop, the event bus / event schema, the
gateway pipeline, and every existing tool are untouched (Constitution IV, VI, X).
There is **no ADR** — plan mode is a decide-stage *policy*, not a runtime-boundary
change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - While planning, non-read-only tools are denied; read-only + allowlist stay usable (Priority: P1)

A run started in plan mode lets the agent investigate freely with read-only tools
(`read_file`, `grep`, `glob_files`, `search_files`) and ask the user questions
(`ask_user`) and submit a plan (`exit_plan_mode`), but **denies** any tool that
would change the world (`write_file`, `edit_file`, `run_command`, …) at the
Gateway's decide stage with a normalized policy-denial. The run stays alive.

**Why this priority**: The read-only guarantee is the whole point of plan mode and
must exist before approval matters; it is the highest-value, must-exist-first
behavior.

**Independent Test**: With an active `PlanModeState`, decide a non-read-only
descriptor (`write_file`) → deny; decide each read-only descriptor (`read_file` /
`grep` / `glob_files` / `search_files`) → allow; decide each allowlisted descriptor
(`ask_user` / `exit_plan_mode`) → allow.

**Acceptance Scenarios**:

1. **Given** plan mode is active, **When** a non-read-only tool (e.g. `write_file`, `run_command`) is decided at the Gateway, **Then** it is denied with a normalized policy-denial and the run continues.
2. **Given** plan mode is active, **When** a read-only tool (`read_file`, `grep`, `glob_files`, `search_files`) is decided, **Then** it is allowed.
3. **Given** plan mode is active, **When** an allowlisted tool (`ask_user`, `exit_plan_mode`) is decided, **Then** it is allowed even though it is not read-only.
4. **Given** a policy in the composed chain raises, **When** a call is decided, **Then** the verdict is deny (fail-closed), never a silent allow.

### User Story 2 - Submit a plan; on approval, plan mode clears and execution proceeds (Priority: P2)

The agent proposes a plan and calls `exit_plan_mode` with the plan text. The plan is
presented to the human through the **existing** interaction round-trip. When the
human **approves**, plan mode is cleared and a subsequent non-read-only tool
(`write_file`) is then **allowed** — the agent executes the plan.

**Why this priority**: Approval is what turns investigation into execution; it is the
core transition plan mode exists to gate.

**Independent Test**: Drive `exit_plan_mode` against a broker scripted to approve;
assert plan mode is now inactive and a subsequent `write_file` decision allows.

**Acceptance Scenarios**:

1. **Given** plan mode is active and a human is attached, **When** `exit_plan_mode` is called with a plan and the human approves, **Then** the plan-mode holder becomes inactive and the tool returns a success result that lets the run proceed.
2. **Given** plan mode has been cleared by an approved `exit_plan_mode`, **When** a non-read-only tool is decided, **Then** it is allowed (the policy is now a no-op).

### User Story 3 - On reject or no human, the run stays in plan mode with a clear outcome (Priority: P3)

When the human **rejects** the plan, or when **no human is attached** to answer, the
run **stays in plan mode** (non-read-only tools remain denied) and `exit_plan_mode`
returns a clear, normalized outcome — never a crash, never a silent state flip.

**Why this priority**: Safe failure is essential: a rejected or unanswered plan must
not silently grant execution.

**Independent Test**: Drive `exit_plan_mode` against a broker scripted to reject, and
against a broker with no reviewer attached; assert plan mode is still active in both
and the tool returns a normalized result (an `ErrorOutput` / a clear "not approved"
message), and a subsequent `write_file` decision still denies.

**Acceptance Scenarios**:

1. **Given** plan mode is active and a human is attached, **When** `exit_plan_mode` is called and the human rejects, **Then** plan mode stays active and the tool returns a clear "plan not approved" outcome.
2. **Given** plan mode is active and **no** human is attached, **When** `exit_plan_mode` is called, **Then** plan mode stays active and the tool returns a clear normalized outcome (no crash, no flip).
3. **Given** any of the above, **When** a non-read-only tool is decided afterward, **Then** it is still denied (plan mode was not cleared).

### User Story 4 - Plan mode off is a no-op (existing behavior unchanged) (Priority: P1)

A run that does not enable plan mode behaves exactly as before: every tool is decided
exactly as it would be with no plan-mode policy at all. The default is off.

**Why this priority**: Additive-and-default-off is a hard constraint (Constitution
X); an existing run must be unaffected.

**Independent Test**: With no `PlanModeState` on the context (or one with
`active=False`), the plan-mode policy allows every tool, including non-read-only
ones — proving an off/absent policy equals no policy. A `RuntimeConfig` without
`plan_mode` builds the same decider it builds today.

**Acceptance Scenarios**:

1. **Given** plan mode is **inactive** (or absent on the context), **When** any tool — read-only or not — is decided, **Then** the plan-mode policy allows it (no-op).
2. **Given** a `RuntimeConfig` with `plan_mode` unset (the default `False`) and no other policy, **When** the decider is built, **Then** it is the same allow-all posture as today (no decider installed for plan mode).

### Edge Cases

- **Plan mode active, non-read-only tool** → denied at the decide stage (policy-denial); it never reaches execution.
- **`exit_plan_mode` while plan mode is inactive** (it was already cleared, or the run was never in plan mode) → it is a harmless allowlisted tool; it still requests a human decision and, on approve, leaves plan mode inactive (idempotent); the decider already allows everything.
- **No reviewer attached** → `exit_plan_mode` returns a clear normalized outcome and does **not** clear plan mode (mirrors `ask_user` returning `None` when no user is available).
- **Reviewer disconnects mid-decision** → the existing broker disconnect semantics resolve the pending question (cancelled); `exit_plan_mode` treats the cancelled/`None` answer as "not approved" and stays in plan mode.
- **Reject** → plan mode stays active; the agent may revise and submit again (a fresh `exit_plan_mode`).
- **Per-run isolation** → the plan-mode holder lives on one run's `RunContext`; one run's plan mode never affects another run/session (the holder is not process-global).
- **Empty / whitespace plan** → still submitted for a human decision; the human can reject (no special-casing in the runtime).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A `plan_mode_policy` decide-stage decider MUST, while plan mode is active, **deny** any tool whose `ToolDescriptor.read_only` is `False`, **except** an allowlist (`ask_user`, `exit_plan_mode`); it MUST **allow** every read-only tool; when plan mode is inactive it MUST **allow** every tool (no-op).
- **FR-002**: The decider MUST decide plan-mode activity by reading **per-run state** carried on the `RunContext` it is given; it MUST NOT use process-global state, and MUST treat an absent holder as inactive (no-op).
- **FR-003**: The `plan_mode_policy` decider MUST be composed into the Gateway's decide stage through the **existing combinators** (`all_of` deny-wins + `safe_failure` fail-closed) in the host's decider builder — **no new gateway stage** is added (Constitution V).
- **FR-004**: A per-run **plan-mode state holder** (`PlanModeState`, a minimal mutable `active: bool`) MUST be the single sharing channel between the decider (which reads it) and the `exit_plan_mode` tool (which flips it); it MUST be created per run and reachable from the `RunContext` both receive.
- **FR-005**: An `exit_plan_mode` tool MUST be added to the Internal Tool Adapter taking a `plan` (text) input; it MUST submit the plan for a human decision by **reusing the existing human round-trip** (the interaction broker that `ask_user` uses) — it MUST NOT invent a new approval path.
- **FR-006**: On a human **approve**, `exit_plan_mode` MUST set the plan-mode holder inactive and return a **success** result that lets the run proceed to execute (it MAY surface the approved plan as context).
- **FR-007**: On a human **reject**, or when **no human is available** (no reviewer attached / the question is cancelled), `exit_plan_mode` MUST leave plan mode **active** and return a clear **normalized** outcome (never a raised exception across the boundary, never a silent flip).
- **FR-008**: `exit_plan_mode` MUST be **allowlisted** by the policy so it is callable while planning, and MUST be marked **not** `read_only` (it mutates run state / requests approval).
- **FR-009**: Entering plan mode MUST be an additive, default-off configuration: a `RuntimeConfig.plan_mode: bool = False` flag (also coerced from a plain mapping) that starts a run with an **active** plan-mode holder; leaving it unset MUST leave existing runs unchanged.
- **FR-010**: The unit MUST be **additive only** — no change to the core agent loop, the gateway pipeline, the event bus, or the event schema, and no change to any existing tool's behavior or any existing descriptor's flags (Constitution IV, VI, X).
- **FR-011**: All enforcement MUST happen at the Gateway **decide stage** (Constitution V); plan mode is a *policy*, never a bypass, and never resolves/executes a tool itself.
- **FR-012**: All new behavior MUST be covered by **deterministic, offline** unit tests (a scripted interaction broker; the internal-tool harness; the governance helpers). The four quality gates MUST stay green.

### Key Entities

- **`plan_mode_policy` decider**: a decide-stage policy that, while plan mode is active, denies non-read-only tools except an allowlist (`ask_user`, `exit_plan_mode`) and allows all read-only tools; a no-op when inactive. Composed deny-wins + fail-closed through the existing combinators. Decides from the descriptor + the per-run holder; never invokes a tool.
- **`PlanModeState`**: a minimal per-run mutable holder (`active: bool`) carried on `RunContext`; read by the decider, flipped by `exit_plan_mode`. Per-run, never process-global.
- **`exit_plan_mode` tool**: an Internal Tool Adapter tool (`plan` input) that submits the plan through the existing human round-trip; clears plan mode on approve, leaves it active and returns a normalized outcome on reject / no human. Allowlisted; not `read_only`.
- **`RuntimeConfig.plan_mode`**: an additive, public-safe flag (default `False`) that starts a run in plan mode.
- **`RunContext.plan_mode`**: the additive field (default `None` = inactive) that carries the per-run holder to the decider and the tool.

### Out of Scope

- A multi-step / structured plan object, plan persistence, or plan history (the plan is free text submitted for a human decision; richer plan modeling is reserved).
- A frontend affordance for plan mode (entering/approving via the web UI) — the runtime seam ships here; a UI is a later unit.
- An event-schema change to surface a dedicated "plan submitted / approved" event (the existing question/answer events already carry the round-trip; a dedicated event would be a versioned VI change with an ADR — not in scope).
- A way to *enter* plan mode mid-run from inside the loop (e.g. a tool that turns plan mode *on*); this unit only **clears** it via `exit_plan_mode` and **enters** it via the config flag.
- Any change to the approval/review boundary, the interaction broker, the core agent loop, the gateway pipeline, or any existing tool.
- Per-tool plan-mode allowlist configuration (the allowlist is fixed to the two tools needed to make and submit a plan).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With plan mode active, a non-read-only tool is denied at the Gateway with a policy-denial while every read-only tool and the allowlist (`ask_user`, `exit_plan_mode`) are allowed, and the run continues.
- **SC-002**: `exit_plan_mode` with an approving human clears plan mode so a subsequent non-read-only tool (`write_file`) is then allowed; with a rejecting / absent human it leaves plan mode active and a subsequent non-read-only tool is still denied, returning a clear normalized outcome either way.
- **SC-003**: With plan mode off (the default), the plan-mode policy is provably a no-op (an off/absent policy decides identically to no policy), and a `RuntimeConfig` without `plan_mode` builds the same decider as today.
- **SC-004**: The change is additive — the core agent loop, the gateway pipeline, the event bus, the event schema, and every existing tool and descriptor are unchanged; the four quality gates (ruff, ruff format, mypy, pytest) stay green with new deterministic offline tests.

## Assumptions

- **One shared `RunContext` per run**: the Gateway hands the decider and the tool the **same** per-run `RunContext` instance, so a holder on it is a sound, additive sharing channel (verified against the real gateway/controller seams; see `research.md`).
- **Reuse the human round-trip**: `exit_plan_mode` reuses the interaction broker that `ask_user` uses (`ask_question` → `list[str] | None`), so it inherits the existing disconnect / no-reviewer semantics and emits the existing question/answer events — no new approval path, no event-schema change.
- **Default-deny is already the house posture**: the policy denies while planning (deny-wins) and fails closed (`safe_failure`), mirroring `network_policy`.
- **Additive and reversible**: removing the `plan_mode_policy`, the `PlanModeState` holder + `RunContext` field, the `exit_plan_mode` tool, the `RuntimeConfig.plan_mode` flag, and the controller wiring leaves the baseline tool set, the gateway, the loop, and every component untouched (Constitution X rollback).
- **No ADR**: plan mode touches neither the Tool Gateway *execution* path (it is a decide-stage policy, V) nor the Event Bus / schema (VI); it does not blur a runtime boundary (IV), so it needs no ADR.
