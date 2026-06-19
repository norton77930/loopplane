# Phase 0 Research: Plan Mode

All decisions favour reuse of the existing Tool Gateway decide-stage seam, the
existing `governance` combinators, the existing per-run `RunContext`, and the existing
human interaction round-trip. The design is additive and default-off. No NEEDS
CLARIFICATION remained from the spec. Every claim below was verified by reading the
real code (file:line cited).

## Seam verification (read before designing)

### S1 — What the decide-stage decider receives (and where it is built)

- `ToolGateway._run_one` calls the decider as
  `await self._decide(call, tool.descriptor, context, emitter)`
  (`src/loopplane/gateway/gateway.py:222`). **The decider receives the per-run
  `RunContext`** (the `context` parameter) and the `ToolDescriptor` — not just the
  call. The `PolicyDecider` shape is `(ToolCallRequest, ToolDescriptor, RunContext,
  EventEmitter) -> PolicyVerdict` (`src/loopplane/approval/decisions.py`,
  `governance/base.py:34`).
- `_build_decider` (`src/loopplane/host/assembly.py:158`) builds the decider **once at
  assembly time**; it becomes `gateway._decide` and is **shared across every session
  and run** (`gateway.py:105`). The spec-034 precedent composes
  `safe_failure(all_of(<approval?>, network_policy))` — deny-wins (`all_of`,
  `combine.py:22`, short-circuits on the first `PolicyDeny`) + fail-closed
  (`safe_failure`, `combine.py:44`, maps any raise to deny). `network_policy`
  (`governance/network.py`) is the exact pattern: an additive decider that gates on a
  `ToolDescriptor` flag, built via `as_decider`, with **no new gateway stage**.

**Implication**: plan mode must (a) be a decider composed the same way, and (b) read
its per-run activity from the `RunContext` it is handed — because the decider object
itself is process-shared, not per-run.

### S2 — `ToolDescriptor.read_only` already exists

- `ToolDescriptor.read_only: bool = False` (`src/loopplane/model/boundary.py:48`).
  Read-only baseline tools: `read_file`, `search_files`, `glob_files`, `grep`
  (`tools/internal.py`; also `web_search`). Non-read-only: `write_file`, `edit_file`,
  `run_command`, `ask_user`, `memory_write` (and `web_fetch`, `read_upload`). Plan mode
  keys off this flag directly — no name lists for the read-only decision.

### S3 — The human round-trip `exit_plan_mode` should reuse

- `ask_user` (`tools/internal.py:565`) does its round-trip via
  `broker = context.interactions; answers = await broker.ask_question(questions)` and
  treats `answers is None` as "no user available / cancelled".
- `InteractionBroker.ask_question` (`src/loopplane/approval/interactions.py:124`)
  returns `list[str] | None`: it returns `None` immediately when **no reviewer is
  attached** (`self._reviewer_attached` is `False`), otherwise it emits
  `question_asked`, awaits the pending event, and returns the answers (and emits
  `question_answered`). On reviewer **disconnect** the pending question is resolved with
  `answers` left `None` (`on_disconnect`, line 58) — so a mid-decision disconnect
  surfaces as `None`, i.e. "not approved". `answer_question(request_id, answers)`
  (line 140) is how a host supplies the human's answer.
- **There is also** `InteractionBroker.request_approval` (line 76) returning an
  `ApprovalResolution` — but it is purpose-built for *escalating a specific tool call*
  (it takes `call_id`/`tool_name`/`input_summary` and emits `approval_requested` /
  `approval_resolved`). For *submitting a plan for a yes/no decision* the question
  round-trip is the better fit, is already used by an internal tool, and yields the
  clean `None` = "no human" semantics. **Decision 3** picks `ask_question`.

### S4 — Where `RunContext` is constructed per run

- `RunContext` is constructed in **exactly one** place in `src`:
  `RuntimeController.drive()` (`src/loopplane/controller/controller.py:344`), once per
  run, with `session_id`, `working_scope`, `cancellation`, `turn_budget`,
  `session_approval_memory`, and `interactions=session.broker`. That **same** context
  object is passed to `session.loop.run(input_blocks, context)` →
  `AgentLoop._execute_calls(..., context)` (`loop/loop.py:200,248,252`) →
  `ToolGateway.execute_batch(..., context=context)` → both `self._decide(..., context,
  ...)` and `tool.adapter.invoke(..., context)` (`gateway.py:222,270`).
- `RunContext` (`src/loopplane/context.py`) is a plain `@dataclass`; it already carries
  mutable per-run state shared with the session (e.g. `session_approval_memory` is the
  session's dict) and an unused `feature_toggles: dict[str, bool]`.

**Implication**: the per-run `RunContext` is the *only* object that is (a) per-run and
(b) handed to **both** the decider and the tool. It is therefore the correct sharing
channel for plan-mode state.

### S5 — Constitution constraints

- **V**: the Tool Gateway is the single enforcement chokepoint; plan mode is a
  decide-stage **policy**, never a bypass; read-only enforcement is at the decide stage.
- **VI**: no event-schema change unless justified/versioned/tested — we make none.
- **IV**: don't blur a runtime boundary; if unavoidable, an ADR — we blur none (we reuse
  the Gateway decide seam, the Internal Tool Adapter SPI, and the existing broker).
- **X**: TDD + rollback — covered by Phase 2 tasks and the plan's rollback note.

## Decision 1 — A new `governance/plan_mode.py`, composed via the existing combinators

- **Decision**: Add `governance/plan_mode.py::plan_mode_policy(state, *, allowlist)`
  returning a `PolicyDecider`. While `state.active`, deny a descriptor with
  `read_only is False` unless its `name` is in `allowlist` (`{"ask_user",
  "exit_plan_mode"}`); allow read-only tools; when `state` is `None` or `state.active`
  is `False`, allow everything. Compose it in `_build_decider` as one more decider in
  `safe_failure(all_of(<approval?>, network_policy, plan_mode_policy(...)))` when plan
  mode is enabled.
- **Why a holder argument rather than reading `context.plan_mode` inside the policy?**
  The decider must read **per-run** state, but the policy is built **once** at assembly.
  Two viable shapes: (a) the policy closure reads `context.plan_mode` at decide time
  (per-call), or (b) the policy is built per-run over a captured holder. Because
  `_build_decider` runs once and the gateway is shared across runs, **(a)** is correct —
  the policy reads the holder **off the `RunContext` it is given at decide time**. The
  `state` parameter form (b) is retained for unit-testability (pass a holder directly),
  and the assembly path uses the `context`-reading form. Concretely `plan_mode_policy`
  takes an optional explicit `state` (tests) and otherwise falls back to
  `context.plan_mode` (assembly) — one function, both call sites. See Decision 2.
- **Rationale**: Mirrors `network_policy` (an additive descriptor-gated decider, no new
  stage, V). `all_of` already gives deny-wins and `safe_failure` already gives
  fail-closed — exactly the required semantics, reused verbatim.
- **Alternatives considered**: A new Gateway stage (rejected: violates V / "reuse the
  existing seam"); a name allow/deny list for read-only (rejected: `read_only` is the
  descriptor's own truth, mirroring 034 Decision 2's rejection of name lists).

## Decision 2 — Per-run state sharing: a holder on `RunContext` (the crux)

- **Decision**: Add a minimal `PlanModeState` dataclass (`active: bool`) and an additive
  `RunContext.plan_mode: PlanModeState | None = None` field (default `None` = inactive).
  The decider reads `context.plan_mode`; `exit_plan_mode` flips `context.plan_mode.active
  = False`. Both receive the **same** per-run `RunContext` (S1, S4), so the flip the tool
  performs is the flip the decider observes on the next call.
- **Rationale**: A closure-shared holder captured at construction would be
  **process-global** (the decider and the `InternalToolAdapter` are each built once and
  shared across all sessions — S1), which is wrong for multi-session isolation. The only
  genuinely per-run object handed to **both** collaborators is `RunContext` (S4), so the
  holder must travel on it. A **dedicated** `PlanModeState` (vs. reusing the generic
  `feature_toggles` dict with a magic key) is explicit, type-checked, and discoverable,
  and lets the tool mutate a single object the decider already holds a reference to.
- **Why a mutable holder, not a bare bool on `RunContext`?** The decider and the tool
  must share **one mutable cell**: the tool flips it and the decider sees the change.
  Re-binding `context.plan_mode = False` would also work (both hold the same `context`),
  but a tiny `PlanModeState` object keeps the intent named and leaves room for the
  decider/tool to share by reference without caring how the field is re-assigned. It is
  the minimal holder the spec asks for.
- **Alternatives considered**: (1) `RunContext.feature_toggles["plan_mode"]` (rejected:
  a stringly-typed magic key, less discoverable, no dedicated type); (2) a closure
  holder shared between `_build_decider` and the adapter at assembly (rejected:
  process-global, breaks per-run/session isolation); (3) thread/context-vars (rejected:
  hidden global state, against the explicit-`RunContext` design, FR-003).

## Decision 3 — `exit_plan_mode` reuses `InteractionBroker.ask_question`

- **Decision**: `exit_plan_mode(plan)` builds a single `Question` ("Approve this
  plan?" carrying the plan text, with options `["approve", "reject"]`), calls
  `context.interactions.ask_question([question])`, and interprets the answer: a first
  answer of `approve` (case-insensitive) → **approve**; anything else, or `None` (no
  reviewer / cancelled) → **not approved**. On approve it sets the holder inactive and
  returns a `TextBlock` confirming execution may proceed (optionally echoing the plan);
  otherwise it leaves the holder active and returns a normalized outcome (an
  `ErrorOutput` for "no user available" — matching `ask_user` — and a clear `TextBlock`
  "plan not approved" for an explicit reject; both leave plan mode active).
- **Rationale**: This is the **existing** human round-trip an internal tool already uses
  (`ask_user`), so it inherits the disconnect/no-reviewer semantics (S3) and emits the
  **existing** question/answer events — **no new approval path, no event-schema change**
  (VI). It returns through the gateway output union (V).
- **Alternatives considered**: `request_approval` (rejected: it is tool-call-escalation
  shaped — `call_id`/`input_summary` + approval events — not a free-form plan decision;
  the question path is the closer, already-reused fit); a brand-new approval event +
  resolver (rejected: an event-schema change requiring an ADR, out of scope).

## Decision 4 — Entering plan mode: an additive `RuntimeConfig.plan_mode` flag

- **Decision**: Add `RuntimeConfig.plan_mode: bool = False` (coerced in
  `from_mapping`). In `host/assembly.py`, when `config.plan_mode` is `True`, pass
  `plan_mode=True` to the `RuntimeController`; `drive()` then constructs `RunContext(...,
  plan_mode=PlanModeState(active=True))`. When `False`, the controller builds the context
  exactly as today (`plan_mode=None`), and `_build_decider` installs **no** plan-mode
  policy for that reason — so an existing run is byte-identical.
- **Rationale**: `RunContext` is built only in `controller.drive()` (S4), so the
  controller is the unavoidable, single per-run wiring point; this mirrors how
  `session_approval_memory`/`interactions` are already wired there. One additive
  constructor kwarg + one line keeps the loop/turn cycle untouched. The flag carries no
  secret (VII).
- **Why also gate the policy installation on the config flag?** `_build_decider` cannot
  see per-run state; gating the *policy installation* on `config.plan_mode` keeps the
  allow-all fast-path (`None`) for runs that never use plan mode and is consistent with
  034's approach of only building a decider when a gate is actually needed. (Even when
  installed, the policy is a no-op for any run whose `RunContext.plan_mode` is `None` —
  so installing it never changes a non-plan-mode run's verdicts; the config gate is an
  optimization + a clean default, not a correctness requirement.)
- **Alternatives considered**: Entering plan mode via a tool that turns it **on**
  (rejected: out of scope — this unit only clears via `exit_plan_mode` and enters via the
  config); a controller method to toggle plan mode mid-run (rejected: scope creep).

## Decision 5 — Test layout

- **Decision**: `tests/unit/test_plan_mode_policy.py` for the policy (using
  `tests/governance_helpers.py`, extended with a small `decide_with_context` that passes
  a real `RunContext`, since this policy reads the context — the existing `decide` passes
  `None` and stays for the context-free policies). `tests/unit/test_plan_mode_tool.py`
  for `exit_plan_mode` (the `_context`/`_invoke` harness from
  `test_internal_file_tools.py` plus a scripted `InteractionBroker` that pre-answers /
  rejects / has no reviewer). Additive assembly tests in
  `tests/contract/test_host_config.py` for the `plan_mode` wiring (decider denies
  `write_file` when active; `from_mapping` round-trip; off-equals-no-policy).
- **Rationale**: Consistent with the repo's governance + internal-tool + host-config test
  patterns; fully offline and deterministic (a scripted broker, no real reviewer, no
  model, no network).
