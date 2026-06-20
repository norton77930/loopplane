---
description: "Task list for Dynamic Subagents (model-driven one-shot spawning) (spec 043)"
---

# Tasks: Dynamic Subagents (model-driven one-shot spawning)

**Input**: Design documents from `/specs/043-dynamic-subagents/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/spawn-subagent.md

**Tests**: REQUIRED (Constitution X). Write tests FIRST and confirm they FAIL before implementing each
unit. Every test is offline and deterministic (`ScriptedModel` for both the parent and the child; the
one-shot subagent `LoopDefinition` harness mirroring `tests/orchestration_helpers.py`; the internal-tool
async-`invoke` drain pattern from `tests/unit/test_plan_mode_tool.py`). No network, no real model.

**Organization**: Grouped by user story (US1 spawn round-trip P1, US2 the hard depth cap P1, US3 failure
containment P2, US4 restricted toolset P3). The additive `RunContext.subagent_depth` field, the
`RuntimeConfig.max_subagent_depth` cap, the controller pass-through, and the test harness are shared
infrastructure US1–US4 depend on.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The additive depth field + cap, the controller pass-through, and the deterministic offline
harness — the foundation every story depends on.

- [ ] T001 In `src/loopplane/context.py`, add an additive `RunContext.subagent_depth: int = 0` field (after `feature_toggles` / before `interactions`, keeping it field-ordered); update the docstring note minimally; no other change.
- [ ] T002 In `src/loopplane/host/config.py`, add an additive `RuntimeConfig.max_subagent_depth: int = 0` field (with a public-safe comment), a `from_mapping` coercion (`int(data.get("max_subagent_depth", 0))`), and a `validate_config` check raising `ConfigError` when `max_subagent_depth < 0`.
- [ ] T003 In `src/loopplane/controller/controller.py`, add an additive `subagent_depth: int = 0` keyword to `RuntimeController.__init__` (store `self._subagent_depth`), and in `drive()` build the `RunContext` with `subagent_depth=self._subagent_depth`. ONLY this per-run wiring — the loop/turn cycle is untouched.
- [ ] T004 Create `tests/subagent_helpers.py`: a deterministic offline harness mirroring `tests/orchestration_helpers.py` — `scripted_child_host(text, *, capacity=100_000) -> LoopPlaneHost`; a `CountingChildHostFactory` recording each `build_child_host(depth, allowed_tools)` call (to prove zero child builds at the cap) and returning a child host whose controller runs at the given depth (via `LoopPlaneHost` + an injected child controller `subagent_depth`); and a `parent_runtime(parent_script, *, child_text="child-done", child_script=None, max_subagent_depth=1, allowed_parent_tools=())` builder that wires a `RuntimeController` over a scripted parent model + a `SpawnSubagentAdapter`, returning `(controller, session_id, collector, factory)`.

**Checkpoint**: The depth field + cap + controller pass-through exist; the offline parent/child harness is
ready. `uv run pytest tests/contract/test_host_config.py -q` still green (additive field).

---

## Phase 2: User Story 1 - The model delegates a focused sub-task (Priority: P1) 🎯 MVP

**Goal**: `spawn_subagent` runs one bounded child through the **existing** `run_loop` and returns the
child's final assistant text to the parent.

**Independent Test**: A scripted parent calls `spawn_subagent({"task": ...})` then emits a final answer;
a scripted child produces known text; the parent's tool result carries the child's known text and the
run completes naturally.

### Tests for User Story 1 ⚠️ (write first, must FAIL)

- [ ] T005 [US1] Create `tests/unit/test_subagent_spawn.py` with a spawn round-trip test: build a parent runtime (`max_subagent_depth=1`) whose parent model scripts `[ToolCallRequest(spawn_subagent, {"task": "do it"}), then TextIncrement("parent final")]` and whose child returns `"child answer"`. Drive the parent; assert the `tool-call-completed` event for `spawn_subagent` has `outcome == "success"` and its output text contains `"child answer"`; assert the run terminates `natural-completion`; assert exactly one child host was built.
- [ ] T006 [US1] In `tests/unit/test_subagent_spawn.py`, assert the descriptor: `SpawnSubagentAdapter(...).describe()` exposes exactly `spawn_subagent` with `read_only is False`, `network is False`, required `task` and optional `allowed_tools` in the schema.

### Implementation for User Story 1

- [ ] T007 [US1] Create `src/loopplane/tools/subagent.py` — `SpawnSubagentAdapter` (a `gateway.spi.ToolAdapter`): `__init__(self, *, build_child_host, max_subagent_depth)` (typed `build_child_host: Callable[[int, tuple[str, ...] | None], LoopPlaneHost]` under `TYPE_CHECKING`); `describe()` returns the single `spawn_subagent` `ToolDescriptor`; `invoke(name, call_input, context)` dispatches to `_spawn`; `shutdown()` is a no-op. `_spawn` (this task, success path only): read `task`; build a child host via the selector (`build_child_host(context.subagent_depth + 1, allowed_tools)`) captured in a holder; build a one-shot `LoopDefinition` (`ManualTrigger`, `StaticInput(task)`, `HostRuntimeProfile(selector=...)`, an always-pass `ValidationPolicy`, `stop_on_pass()` with `max_iterations(1)` as the stop condition, `ObservationPolicy(emit_loop_events=True)`); `outcome = await run_loop(definition)` with **no** `on_loop_event`; recover the final assistant text from `host.history_snapshot(outcome.state.run_refs[-1].session_id)` (join the last assistant entry's `TextBlock`s); append a metadata-only child-event-count line via `loopplane.orchestration.aggregate_events([SubagentResult(...)])`; `yield TextBlock(text=...)`.
- [ ] T008 [US1] Export `SpawnSubagentAdapter` from `src/loopplane/tools/__init__.py` (additive `__all__`, alphabetically placed) and add a matching `- \`SpawnSubagentAdapter\` — …` bullet under the `### \`loopplane.tools\`` section of `docs/api-reference.md` (keep the bijection — `tests/contract/test_api_reference.py`).
- [ ] T009 [US1] In `src/loopplane/host/assembly.py`, when `config.max_subagent_depth >= 1`, build a `build_child_host(depth, allowed_tools)` closure (a child `RuntimeConfig` = the parent config with the spawn adapter excluded from the child's `tool_adapters` and, if `allowed_tools` given, its `tools`/`tool_adapters` filtered to that allowlist; then `LoopPlaneHost`/a child `RuntimeController` started at `subagent_depth=depth`) and register a `SpawnSubagentAdapter(build_child_host=…, max_subagent_depth=config.max_subagent_depth)` on the gateway; also pass `subagent_depth=0` to the top-level `RuntimeController` (explicit, the default). Gate strictly on `>= 1` so `0` leaves the runtime unchanged.
- [ ] T010 [US1] Run `uv run pytest tests/unit/test_subagent_spawn.py -q` and confirm the US1 tests pass.

**Checkpoint**: The model-driven one-shot spawn works end-to-end through the existing `run_loop` (MVP).

---

## Phase 3: User Story 2 - Bounded recursion: the hard depth cap (Priority: P1) 🎯 SAFETY

**Goal**: At/over `max_subagent_depth`, `spawn_subagent` is denied with a normalized error and **no**
child run is created; a child runs at parent depth + 1.

**Independent Test**: A parent at `subagent_depth == max_subagent_depth` that calls `spawn_subagent` →
a normalized error tool result; the counting factory built **0** child hosts; the parent run continues.

### Tests for User Story 2 ⚠️ (write first, must FAIL)

- [ ] T011 [US2] In `tests/unit/test_subagent_spawn.py`, add the depth-cap denial test: build a parent runtime with `max_subagent_depth=1` but start the parent controller at `subagent_depth=1` (equal to the cap); script the parent to call `spawn_subagent`. Assert the `tool-call-completed` for `spawn_subagent` has `outcome == "failure"` with a `POLICY_DENIAL`-or-`EXECUTION` normalized error whose message names the depth cap; assert the counting factory built **0** child hosts (no unbounded nesting); assert the parent run still terminates (does not crash).
- [ ] T012 [US2] In `tests/unit/test_subagent_spawn.py`, add the child-depth test: with `max_subagent_depth=2` and a top-level parent (depth 0), spawn a child; assert the factory was called with `depth == 1` (child = parent + 1). Add the default-cap nesting test: with `max_subagent_depth=1`, a child (depth 1) that itself scripts a `spawn_subagent` is denied with **0** grandchild builds.

### Implementation for User Story 2

- [ ] T013 [US2] In `src/loopplane/tools/subagent.py`, add the depth guard at the top of `_spawn`: if `context.subagent_depth >= self._max_subagent_depth`, `yield ErrorOutput(category=ErrorCategory.POLICY_DENIAL, message=f"subagent depth cap reached ({self._max_subagent_depth}); refusing to spawn")` and `return` BEFORE building any `LoopDefinition` or calling the child-host factory / `run_loop`. Fail-safe: the deny is the first thing checked; no child run is created.
- [ ] T014 [US2] Run `uv run pytest tests/unit/test_subagent_spawn.py -q` and confirm the depth-cap tests pass (zero child builds at/over the cap).

**Checkpoint**: Unbounded nesting is impossible — proven by zero child builds at the cap.

---

## Phase 4: User Story 3 - A failing child is contained (Priority: P2)

**Goal**: A child that raises, terminates non-naturally, pauses, or answers empty → a normalized error
to the parent; the parent never crashes.

**Independent Test**: A child whose model raises → the parent's `spawn_subagent` result is a normalized
error; the parent run does not crash and can take a subsequent turn.

### Tests for User Story 3 ⚠️ (write first, must FAIL)

- [ ] T015 [US3] In `tests/unit/test_subagent_spawn.py`, add a raising-child test: the child model is `ScriptedFailure(RuntimeError("boom"))`. Assert the `spawn_subagent` result is `outcome == "failure"` with a public-safe normalized error (the message contains neither `"boom"` nor a traceback); assert the parent does not crash and (with a parent script that takes another turn after the tool result) the parent run completes.
- [ ] T016 [US3] In `tests/unit/test_subagent_spawn.py`, add an empty-answer test: a child that produces a `TurnEnd` with no text. Assert a clear normalized result (a `failure` error or a non-crashing empty marker), never an exception.

### Implementation for User Story 3

- [ ] T017 [US3] In `src/loopplane/tools/subagent.py`, wrap `run_loop` (mirroring unit 013's coordinator): on `except Exception`, `yield ErrorOutput(message="subagent run failed")` (a fixed public-safe marker; never the raw exception) and `return`. After a successful `run_loop`, if `outcome.terminal_event != "loop_completed"` or `outcome.paused` → `yield ErrorOutput(message=f"subagent did not complete ({outcome.stop_reason or 'no result'})")`; if the recovered final text is empty → `yield ErrorOutput(message="subagent produced no answer")`. The parent run continues regardless.
- [ ] T018 [US3] Run `uv run pytest tests/unit/test_subagent_spawn.py -q` and confirm the containment tests pass.

**Checkpoint**: A child failure is always a normalized, public-safe result; the parent is never crashed.

---

## Phase 5: User Story 4 - A restricted child toolset + events isolation (Priority: P3)

**Goal**: `allowed_tools` restricts the child's tools to the parent∩allowlist; the child's events never
reach the parent's live bus.

**Independent Test**: Spawn a child with `allowed_tools=["read_file"]`; the child host registers only the
allowlisted tool(s). Separately: the parent's collected events contain no child loop events.

### Tests for User Story 4 ⚠️ (write first, must FAIL)

- [ ] T019 [US4] In `tests/unit/test_subagent_spawn.py`, add a restricted-toolset test: with a parent runtime whose host-declared `config.tools` include e.g. `alpha` + `beta` (individually-registered `ToolSpec`s) plus a bundled multi-tool `InternalToolAdapter`, restrict with `allowed_tools=["alpha"]`; assert the built child host's `inspect_tools()` lists `alpha` and not `beta`, that the bundled adapter is dropped whole (its tools absent), and that `spawn_subagent` is not re-granted to the child.
- [ ] T020 [US4] In `tests/unit/test_subagent_spawn.py`, add an events-isolation test: assert none of the parent collector's events are child loop events (no event whose `session_id` equals the child run's session id) — the child events are captured only in the (metadata-only) aggregation appended to the result; assert no `SCHEMA_VERSION`-affecting new event type appears.

### Implementation for User Story 4

- [ ] T021 [US4] In `src/loopplane/host/assembly.py` add `_restrict_config(config, allowed_tools)` used by the `build_child_host` closure: when `allowed_tools` is given, filter the child `RuntimeConfig.tools` by `spec.descriptor.name`, and keep a `tool_adapter` only when **every** tool it advertises is allowlisted (else drop it whole — least privilege errs safe; **no out-of-gateway adapter wrapping / `.invoke` delegation**, so the Tool Gateway stays the single owner of tool dispatch, V, and the `test_no_execution_path_outside_the_gateway` audit stays green). Set the child's `max_subagent_depth` to the parent's only when `"spawn_subagent"` is allowlisted (else 0), so the spawn tool is not re-granted to a restricted child. Keep it additive — the parent runtime is unaffected.
- [ ] T022 [US4] Run `uv run pytest tests/unit/test_subagent_spawn.py -q` and confirm the restricted-toolset + events-isolation tests pass.

**Checkpoint**: Least-privilege delegation works; the parent's live event bus is uncorrupted (VI).

---

## Phase 6: Assembly gating, tracking & polish

- [ ] T023 In `tests/unit/test_subagent_spawn.py`, add an assembly-gating test: `LoopPlaneHost(RuntimeConfig(model=…, max_subagent_depth=0))` registers **no** `spawn_subagent` (assert it is absent from `host.inspect_tools()`); `max_subagent_depth=1` registers it.
- [ ] T024 Update tracking: `.specify/feature.json` → `{"feature_directory":"specs\\043-dynamic-subagents"}`; `CLAUDE.md` SPECKIT block → `specs/043-dynamic-subagents/plan.md`.
- [ ] T025 In `CHANGELOG.md`, add a `- **043** …` entry to the `## [Unreleased]` `### Added` list (after the 042 entry) describing the additive, reuse-first, depth-capped model-driven one-shot spawn. Keep `tests/contract/test_changelog.py` green (`## [0.1.0]` + units 001–013 still present).
- [ ] T026 Update `docs/loopplane-agent-board.md`: add a `043-dynamic-subagents` row to §3 and update §4.
- [ ] T027 Run the full gate suite and iterate to green: `uv run ruff check .`; `uv run ruff format .` then `uv run ruff format --check .`; `uv run mypy`; `uv run pytest -q`. (A pre-existing flaky `tests/integration/test_examples_smoke.py` subprocess-timeout may fail only under full-suite load — if it is the ONLY failure and passes in isolation, that is the known flake, not this change.)

**Checkpoint**: All four gates green; tracking + docs updated; feature additive and reversible
(`max_subagent_depth=0` disables it).

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → blocks everything (the depth field, the cap, the controller pass-through, the
  harness).
- **US1 (Phase 2)** → the MVP; the adapter + assembly wiring the other stories extend.
- **US2 (Phase 3)** → the safety cap; depends on US1's adapter (adds the guard at the top of `_spawn`).
- **US3 (Phase 4)** → containment; depends on US1's `run_loop` call (wraps it).
- **US4 (Phase 5)** → restricted toolset + events isolation; depends on US1's child-host factory.
- **Phase 6** → tracking/docs/gates; last.

## Parallel Opportunities

- T001, T002, T003 touch different files (context / config / controller) and can be written together,
  then T004 (harness) after.
- Within each user story, the test task precedes its implementation task (TDD).
- The doc/tracking tasks (T024–T026) are independent of each other.
