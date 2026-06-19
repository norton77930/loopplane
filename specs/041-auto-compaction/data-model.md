# Phase 1 Data Model: Configurable Proactive Auto-Compaction

No new persisted entities, no event/content/usage-shape change. The unit adds one
config field, one assembler constructor parameter (+ a tiny effective-capacity
helper), and one controller constructor parameter that threads the first into the
second.

## Reused (unchanged)

- **`compact_history(history, *, keep_last)`** (`loopplane.loop.compaction`) —
  the mechanical compaction. Produces a `SummaryMarkerBlock(digest=SummaryDigest(
  turn_count, tool_names, excerpts))`; never splits a tool call from its result;
  returns `False` when there is nothing worth compacting. **Reused verbatim** by
  the proactive path; output **unchanged**.
- **`PromptAssembler._estimate_tokens(request)`** — the size heuristic: `sum of
  TextBlock char-lengths + 50 per non-text block, // chars_per_token (4)`.
  **Reused unchanged** for the proactive estimate.
- **`ModelBoundary.context_capacity() -> int`** — the model's full context window.
  Unchanged; the threshold multiplies it.
- **`SessionHistory.replace_prefix`** — compaction's in-memory prefix replacement;
  does not invoke the recording hook (durable stream keeps the originals).
  Unchanged.
- **The reactive `ContextOverflowError` path** in `AgentLoop.run` — compact +
  retry once. Unchanged.

## Modified

### `RuntimeConfig` (`loopplane.host.config`)

Add one additive field, alongside `plan_mode` / `allow_network` /
`permission_rules`:

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `auto_compact_threshold` | `float \| None` | `None` | When `None`, proactive pre-send compaction uses the model's **full** capacity (the existing behavior; off). When a value `f` in `(0, 1]`, proactive compaction runs once before the model call whenever the estimated assembled-context size reaches `f * context_capacity()`. Carries no secret. |

- `from_mapping`: coerce `data.get("auto_compact_threshold")` to `float` when
  present and not `None`, else `None`.
- `validate_config`: when not `None`, require a **finite** number with
  `0 < f <= 1`; otherwise raise `ConfigError` (public-safe, field-level).

### `PromptAssembler.__init__` (`loopplane.loop.assembly`)

Add one additive keyword parameter:

| Param | Type | Default | Meaning |
|------|------|---------|---------|
| `compact_threshold` | `float \| None` | `None` | The proactive-compaction threshold fraction. Stored as `self._compact_threshold`. `None` → `_effective_capacity` returns the full capacity (today's behavior). |

New private helper (internal — not exported):

```text
_effective_capacity(capacity: int) -> int
    return capacity if self._compact_threshold is None
           else int(capacity * self._compact_threshold)
```

The existing proactive check in `assemble` changes only its comparator:

```text
# before:  if self._estimate_tokens(request) > capacity and compact_history(...):
# after:   if self._estimate_tokens(request) > self._effective_capacity(capacity) \
#              and compact_history(...):
```

Everything else in `assemble` (augmentation, re-establishment, `_compose`,
`mark_compacted` flow) is unchanged.

### `RuntimeController.__init__` (`loopplane.controller.controller`)

Add one additive keyword parameter:

| Param | Type | Default | Meaning |
|------|------|---------|---------|
| `auto_compact_threshold` | `float \| None` | `None` | Stored as `self._auto_compact_threshold`; passed to the per-session `PromptAssembler(compact_threshold=...)` in `_assemble`. `None` → the assembler keeps today's full-capacity proactive check. |

### `assemble()` (`loopplane.host.assembly`)

Thread the config field into the controller, matching the existing kwargs pattern
(only added when not `None`, like the other optional controller kwargs):

```text
if config.auto_compact_threshold is not None:
    controller_kwargs["auto_compact_threshold"] = config.auto_compact_threshold
```

## New (internal — not exported)

- `PromptAssembler._effective_capacity` — the threshold→effective-capacity helper
  (a method, no new public name).

No new public package, class, or `__all__` entry (FR-011).

## Validation / behavior rules

- FR-002: `auto_compact_threshold is None` → `_effective_capacity == capacity` →
  the pre-send check is the exact `> capacity` shipped today (byte-identical off).
- FR-003: `auto_compact_threshold = f in (0, 1]` → the check uses
  `int(capacity * f)`; `compact_history` runs once when the estimate exceeds it.
- FR-004/FR-006: the digest and the size heuristic are the existing functions,
  unchanged.
- FR-005: an invalid threshold (`<= 0`, `> 1`, non-finite) → `ConfigError` at
  assembly.
- FR-008: the field round-trips through `from_mapping` and carries no secret.
- FR-010/FR-011: no event emitted; no new public name (`auto_compact_threshold`
  is a field on the existing `RuntimeConfig`; the assembler/controller gain only
  constructor parameters; `_effective_capacity` is a private method).
