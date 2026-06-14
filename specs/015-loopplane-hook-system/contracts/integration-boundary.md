# Contract: Hook Integration Boundary

How the hook system attaches to the existing runtime **without** changing any
component's required public surface and without crossing a runtime boundary
(Constitution IV/V/VI). Every seam below is an **optional** parameter defaulting
to "no hooks".

## Tool Gateway (Constitution V)

`ToolGateway.__init__` gains an optional `hooks: HookDispatcher | None = None`
(alongside the existing optional `decide` / `artifact_handoff`). Inside
`_run_one`, in stage order:

1. resolve → validate → `decide` (unchanged).
2. **before_tool_use** fires only on the allow path, after `decide`. A `Deny`
   returns the existing `_failure(POLICY_DENIAL)`; a `Modify` replaces the input
   and **re-runs `validate_input`** before execution.
3. execute (unchanged).
4. on success → **after_tool_use**; if the descriptor is write/edit-class →
   **file_changed**.
5. on execution/timeout failure → **after_tool_failure**.

The Gateway remains the only component that resolves/authorizes/executes tools;
hooks observe or decide but never call a tool or bypass the Gateway (FR-009).

## Agent Loop (Constitution VI)

`AgentLoop.__init__` gains optional `hooks` and a per-session-start signal. In
`run`:

- **user_prompt_submit** fires after input is received and before the first model
  turn; a `Block` ends the run without a model call (surfaced as a normalized
  termination), an `Annotate` augments the assembled prompt.
- **model_stop** fires at `natural-completion`, before/with the terminal event.

The Loop still emits only normalized events; hook firing is a **separate** call
path and never re-emits or mutates the event bus (FR-010). Hook failures use the
Loop's existing emitter `diagnostic` only.

## Runtime Controller (Constitution IV)

`RuntimeController.__init__` gains optional `hooks: HookRegistry | None = None`.
The controller:

- builds one `HookDispatcher` from the registry and injects it into each session's
  Gateway, Loop, and the Coordinator;
- fires **process_setup** at most once per controller lifetime;
- fires **session_start** on the first `drive` of a session and **session_end** on
  `terminate`/`detach`;
- owns the registry as the single registration surface for hosts and plugins.

## Orchestration Coordinator (unit 013, additive)

`Coordinator` gains an optional `hooks` dispatcher and fires **subagent_start**
before, and **subagent_stop** after, each delegated `run_loop`. The coordinator
continues to drive subagents through the public Phase-3 loop surface; hooks observe
only (FR-019). When no subagents run, these points never fire.

## Non-goals on this boundary

- No component gains a **required** parameter; all hook seams are optional and
  default-absent (so 001/002/013 public contracts are not rewritten — stop §9.5).
- Hooks do not persist, do not appear in checkpoints, and are not replayed.
- The event bus gains **no** new event type; hook failures reuse `diagnostic`.
