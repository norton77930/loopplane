# Contract: Public Hook API (`loopplane.hooks`)

The public surface a host or plugin uses. Everything here is in-process and
metadata-only.

## Registry

```
class HookRegistry:
    def register(point: LifecyclePoint, callback: HookCallback) -> None
    def unregister(point: LifecyclePoint, callback: HookCallback) -> bool
    def clear(point: LifecyclePoint | None = None) -> None
```

- **register** appends `callback` to `point`'s ordered list (FIFO firing — FR-003).
  The same callback may be registered more than once; each registration fires.
- **unregister** removes the first matching registration; returns whether one was
  removed.
- **clear** drops all callbacks for `point`, or for every point when `point` is
  omitted.
- Registration/removal is safe at any time; a change takes effect on the **next**
  firing of that point and never mutates an in-flight firing (FR-018).

## Callback

```
HookCallback = Callable[[Payload], None | Decision]   # sync or async (FR-004)
```

- For an **observational** point the return value is ignored.
- For a **gating** point the callback returns the point's `*Decision`; returning
  `None`/unrecognized, or raising, is an **abstain** (FR-016).

## Dispatcher firing semantics

Observational points (`fire`):

- All registered callbacks fire in registration order (FR-003).
- A callback that raises or hangs is isolated — the run is unaffected (FR-005) and
  the failure is reported once via the diagnostic channel as a public-safe,
  metadata-only warning naming the point (no exception text, no input — FR-015).

Gating points (`decide_tool`, `decide_prompt`):

- Callbacks run in registration order.
- **Resolution** (FR-017): any `Deny`/`Block` short-circuits to deny/block;
  otherwise `Modify`/`Annotate` results **compose in order** (a later callback sees
  the running modified input / accumulated annotation); absent any opinion the
  result is `Allow`.
- A raising/malformed gating callback abstains (does not change the running
  decision) and is reported via the diagnostic channel (FR-016).
- `before_tool_use`: a final `Modify` input is **re-validated** against the tool
  schema before execution; a `Deny` maps to the Gateway's normalized
  `POLICY_DENIAL` failure (FR-008, FR-012).
- `user_prompt_submit`: a `Block` prevents the model call and surfaces a
  public-safe reason; an `Annotate` augments the prompt the model receives (FR-007).

## Decisions

```
ToolGateAllow() | ToolGateDeny(reason: str) | ToolGateModify(input: dict)
PromptAllow()   | PromptBlock(reason: str)  | PromptAnnotate(text: str)
```

`reason`/`text` MUST be public-safe (FR-015). The Gateway/Loop, not the callback,
apply the decision's effect.

## Default-inert guarantee

With no `HookRegistry` configured (or an empty one), every component runs its
existing path with no dispatcher work and no added latency (FR-011, FR-020,
SC-003).
