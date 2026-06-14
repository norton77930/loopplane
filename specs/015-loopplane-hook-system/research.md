# Phase 0 Research: Lifecycle Hook System

Seam analysis grounded in the existing runtime (units 001/003/013). Every
decision below is re-derived for LoopPlane, not copied from any reference
(Constitution IX).

## R1 — Where each lifecycle point attaches

| Point | Real seam | Trigger |
|---|---|---|
| before-tool-use | `gateway.ToolGateway._run_one`, after Stage 3 `decide`, before Stage 4 execute | per resolved+validated+allowed call |
| after-tool-use | `_run_one`, on a `success` `ToolResultBlock` | per successful call |
| after-tool-failure | `_run_one`, on the execution/timeout `_failure` branch | per failed call (execution/timeout only) |
| file-changed | `_run_one`, after a successful call whose descriptor is write/edit-class | per successful write/edit |
| user-prompt-submit | `loop.AgentLoop.run`, after input received, before the model turn loop | per run input |
| session-start | `controller.RuntimeController.drive`, first drive of a session | once per session |
| session-end | `controller` `terminate` / `detach` (suspend) | per session close |
| process-setup | `controller.RuntimeController` construction / first session | at most once per runtime |
| model-stop | `loop.run`, at `natural-completion` termination | per natural stop |
| subagent-start | `orchestration.coordinator`, before a delegated `run_loop` | per subagent |
| subagent-stop | `orchestration.coordinator`, after a delegated run finishes | per subagent |

**Decision**: the Gateway, Loop, Controller, and Coordinator each receive one
optional `hooks` dispatcher (default `None`). This mirrors the Gateway's existing
optional `decide` / `artifact_handoff` seams, keeping the change additive and the
un-hooked path identical (FR-011, SC-003). No existing required parameter changes,
so unit 001/002 public contracts are not rewritten (stop-condition §9.5 avoided).

## R2 — Gating decision types are distinct from `PolicyVerdict`

The approval layer's `PolicyVerdict = PolicyAllow | PolicyDeny` carries only
allow/deny. A before-tool hook additionally needs **modify**, and prompt-submit
needs **annotate**. **Decision**: introduce two small decision families in
`hooks.decisions` — `ToolGateDecision` (`allow` / `deny(reason)` / `modify(input)`)
and `PromptDecision` (`allow` / `block(reason)` / `annotate(text)`) — rather than
overloading `PolicyVerdict`. A hook **deny** is then mapped by the Gateway onto its
existing `NormalizedError(category=POLICY_DENIAL, reason=...)` `_failure` path so
the denial is surfaced exactly like an approval denial (FR-008). Keeping the
types separate preserves the approval layer's boundary (it is unaware of hooks).

## R3 — Firing order relative to approval (FR-012)

The before-tool hook fires **after** Stage 3 `decide` and only on the allow path
(a `PolicyDeny` short-circuits before any hook runs). Therefore a hook can never
widen what approval denied; it can only further restrict (deny) or adjust inputs
(modify) of an already-allowed call. After a hook `modify`, validation has already
run against the original input — **Decision**: re-validate the modified input
against the tool's `input_schema` before execution, so a hook cannot smuggle a
schema-invalid call past the Gateway's Stage 2 guarantee.

## R4 — Failure isolation surfaces through the existing diagnostic event (VI)

A raising or slow hook must never crash the run (FR-005) and must surface as
metadata-only (FR-015). **Decision**: the dispatcher catches every hook exception
and forwards a public-safe summary through the **existing** `EventEmitter.diagnostic`
("warning", category `"hooks"`, a fixed message naming the point — never the raw
exception). This reuses the normalized event the runtime already emits, so hooks
introduce **no new event type and no dependence of event emission on hooks** (VI).
The dispatcher records only the point name and a generic reason — never the
callback's exception text, the tool input, or any path.

## R5 — Gating fail-safe = abstain-to-baseline (FR-016)

A gating hook that raises or returns a malformed decision **abstains**: the
dispatcher treats it as "no opinion" and the run proceeds with the decision it
would have made without that hook. This never fails open (it cannot turn a baseline
deny into an allow) and never aborts. Across multiple gating hooks the resolution
is: **any deny/block wins**; **modifications/annotations compose in registration
order** (a later hook observes earlier modifications) (FR-017). This is a
deliberate divergence from reference systems that let a hook error block the call;
LoopPlane chooses zero-surprise preservation of baseline behavior.

## R6 — FileChanged signal source

The Gateway sees `ToolDescriptor`, not file semantics. **Decision**: detect
write/edit-class tools via a descriptor capability tag (the model boundary's
`ToolDescriptor` already carries capability metadata used elsewhere; reuse it
rather than hard-coding tool names). The file-changed point fires only after such a
tool returns `success` (FR-013), carrying the changed path's identity as
metadata. If a descriptor declares no write/edit capability, the point never fires
for it — no false positives.

## R7 — Sync + async callbacks

Callbacks may be plain functions or coroutines. **Decision**: the dispatcher
detects coroutine functions (`inspect.iscoroutinefunction`) and awaits them;
synchronous callbacks are called directly. All firing happens within the existing
async call path, so no new threads or event loops are introduced (anyio-only).

## R8 — Ownership and registration surface (IV)

**Decision**: the `HookRegistry` is owned by the `RuntimeController` (one per
runtime). The controller builds a `HookDispatcher` from the registry and passes it
into each session's Gateway/Loop and into the Coordinator. Hosts register hooks on
the registry before driving a session; the plugin system (unit 016) will register
through the same registry. Registration mutations take effect on the next firing of
a point and never mutate an in-flight firing (FR-018) — the dispatcher snapshots
the callback list per fire.
