# Phase 1 Data Model: Lifecycle Hook System

All types live in `loopplane.hooks`. Payloads are frozen, metadata-only, and
public-safe (FR-015). No type holds raw tool output, raw exception text, secrets,
or absolute private paths.

## LifecyclePoint

A string-valued enum naming the eleven points (FR-002):

```
before_tool_use, after_tool_use, after_tool_failure, user_prompt_submit,
session_start, session_end, process_setup, subagent_start, subagent_stop,
file_changed, model_stop
```

Points are classified as **gating** (`before_tool_use`, `user_prompt_submit`) or
**observational** (the other nine).

## Payloads (frozen dataclasses, metadata-only)

| Point | Payload fields |
|---|---|
| before_tool_use | `session_id`, `call_id`, `tool_name`, `input` (the call inputs, read-only view) |
| after_tool_use | `session_id`, `call_id`, `tool_name`, `outcome="success"`, `duration_seconds` |
| after_tool_failure | `session_id`, `call_id`, `tool_name`, `error_category`, `reason` (public-safe) |
| file_changed | `session_id`, `call_id`, `tool_name`, `path` (changed file identity) |
| user_prompt_submit | `session_id`, `text` (the submitted prompt text) |
| session_start | `session_id`, `label` |
| session_end | `session_id`, `state` |
| process_setup | (no fields) |
| subagent_start | `session_id`, `subagent`, `agent_type` |
| subagent_stop | `session_id`, `subagent`, `outcome` |
| model_stop | `session_id`, `turns_taken` |

> `input` and `text` are carried because the gating points operate on them; the
> dispatcher exposes them read-only and applies a hook's `modify`/`annotate`
> result rather than letting a callback mutate the payload in place.

## Gating decisions (`hooks.decisions`)

```
# before_tool_use
ToolGateAllow()                       # no opinion / allow
ToolGateDeny(reason: str)             # block the call; reason is public-safe
ToolGateModify(input: dict)           # replace the call inputs (re-validated)

ToolGateDecision = ToolGateAllow | ToolGateDeny | ToolGateModify

# user_prompt_submit
PromptAllow()
PromptBlock(reason: str)
PromptAnnotate(text: str)             # appended/prepended context for the model

PromptDecision = PromptAllow | PromptBlock | PromptAnnotate
```

A gating hook returns the relevant decision type. Returning `None`, raising, or
returning an unrecognized value is treated as **abstain** (= the `*Allow` baseline)
per FR-016.

## HookCallback

A caller-supplied `Callable` — synchronous or asynchronous (R7). For an
observational point its return value is ignored. For a gating point it returns the
point's `*Decision`. Signature: `callback(payload) -> None | Decision`.

## HookRegistry

Owned by the `RuntimeController` (R8). Operations (FR-001):

- `register(point: LifecyclePoint, callback: HookCallback) -> None`
- `unregister(point: LifecyclePoint, callback: HookCallback) -> bool`
- `clear(point: LifecyclePoint | None = None) -> None`
- internally: ordered (FIFO) list of callbacks per point (FR-003).

## HookDispatcher

Built from a registry; passed into Gateway/Loop/Controller/Coordinator as the
optional `hooks` seam. Responsibilities:

- `fire(point, payload) -> None` for observational points: snapshot the callback
  list, invoke each in order, isolate failures via the diagnostic channel (R4).
- `decide_tool(payload) -> ToolGateDecision` and `decide_prompt(payload) ->
  PromptDecision` for gating points: run callbacks in order, **deny/block wins**,
  **modify/annotate composes in order**, abstain on failure (R5, FR-016, FR-017).
- A `None` dispatcher (no hooks) is the zero-overhead path: components guard every
  fire with a cheap "is the seam present and non-empty?" check (FR-011).

## Relationships

```
RuntimeController ──owns──> HookRegistry ──builds──> HookDispatcher
HookDispatcher ──passed into──> ToolGateway, AgentLoop, Coordinator
HookDispatcher ──reports failures via──> EventEmitter.diagnostic   (existing event; VI)
ToolGateDeny ──mapped onto──> NormalizedError(POLICY_DENIAL)        (existing path; FR-008)
```
