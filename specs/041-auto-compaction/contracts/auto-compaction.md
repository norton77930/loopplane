# Contract: Configurable Proactive Auto-Compaction

This contract pins the observable behavior of the configurable proactive
auto-compaction threshold. It is enforced by `tests/unit/test_auto_compaction.py`
(and leaves the existing compaction/overflow tests in
`tests/integration/test_us4_memory_skills.py` and `tests/unit/test_loop_core.py`
green, unchanged).

## C1 — Threshold set: proactive compaction at `f * capacity`

When `auto_compact_threshold = f` (in `(0, 1]`) and the estimated assembled-context
size is `> int(capacity * f)`, the assembler runs `compact_history` once **before**
the model call and rebuilds the request. The request the model receives carries a
`SummaryMarkerBlock` (the compacted prefix), and no `ContextOverflowError` is
raised by the model on that turn.

## C2 — Threshold set: no compaction below the threshold

When `auto_compact_threshold = f` and the estimated size is `<= int(capacity * f)`,
no proactive compaction runs; the request carries no `SummaryMarkerBlock` (unless
one was already present from an earlier turn).

## C3 — Default `None`: byte-identical to today

When `auto_compact_threshold = None` (the default), the effective capacity is the
**full** `context_capacity()`. The proactive check is then the exact `> capacity`
comparison shipped today:

- an estimate `<= capacity` → **no** proactive compaction (identical to today);
- an estimate `> capacity` → the existing full-capacity proactive compaction
  still runs once (the pre-threshold behavior is preserved).

## C4 — `_effective_capacity` computation

`_effective_capacity(capacity)` returns `capacity` when the threshold is `None`,
and `int(capacity * threshold)` otherwise. (`threshold = 1.0` → `capacity`;
`threshold = 0.5`, `capacity = 1000` → `500`.)

## C5 — Reactive backstop unchanged

Regardless of the threshold (including `None`), the loop's reactive
`ContextOverflowError` path is unchanged: a single overflow → compact + retry once
→ success; a second overflow → run terminates `unrecoverable-error`.

## C6 — `compact_history` reused, digest unchanged

The proactive path invokes the **existing** `compact_history` with the existing
`keep_last`; the produced `SummaryMarkerBlock` / `SummaryDigest` is identical to
the reactive path's. No new compaction algorithm; the digest output is unchanged.

## C7 — Invalid threshold rejected fast

`validate_config` (and therefore `LoopPlaneHost` / `assemble`) raises `ConfigError`
for an `auto_compact_threshold` that is not `None` and not a finite number in
`(0, 1]` (`0`, negative, `> 1`, `NaN`, `inf`). The message is public-safe and
field-level.

## C8 — Config wiring & no secret

`RuntimeConfig.auto_compact_threshold` round-trips through `from_mapping`
(coerced to `float` or `None`), defaults to `None`, and is **not** a secret field
(the no-secret config contract stays green). It is threaded into the
`RuntimeController` and the per-session `PromptAssembler` via the existing
`assemble()` wiring.

## C9 — No boundary / schema change

No event-schema, content-model, or `TokenUsage`-shape change; compaction emits no
event (proactive or reactive); no change to the agent loop's turn cycle, the
runtime core, the Tool Gateway, or the Event Bus; no new public package or
`__all__` name.
