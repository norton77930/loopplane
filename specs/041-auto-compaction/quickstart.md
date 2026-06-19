# Quickstart: Configurable Proactive Auto-Compaction

LoopPlane compacts conversation history to stay within a model's context window.
By default it compacts **reactively** — only when the model rejects an oversized
turn (`ContextOverflowError`), the loop compacts and retries once — plus a
built-in proactive check that compacts when the estimated context exceeds the
model's **full** capacity.

This unit lets you compact **earlier**, on a safety margin, with one additive
config field.

## Default (off — today's behavior)

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig

host = LoopPlaneHost(RuntimeConfig(model=model))
# auto_compact_threshold defaults to None: proactive compaction uses the model's
# full context capacity (the existing behavior), and the reactive overflow
# backstop still applies. Nothing changes.
```

## Compact proactively at a fraction of capacity

```python
host = LoopPlaneHost(
    RuntimeConfig(model=model, auto_compact_threshold=0.8)
)
# Before each turn, if the estimated assembled context reaches 80% of the model's
# context_capacity(), the runtime compacts history once (the same mechanical
# digest used reactively) *before* sending — so the overflow is avoided.
```

Choose the fraction by how much head-room you want before the hard limit:

- `0.9` — compact late, close to the window (more context retained per turn).
- `0.7`–`0.8` — a comfortable safety margin (recommended starting point).
- `1.0` — equivalent to the default trigger (compact only at the full window).
- `None` — off (the default; full-capacity proactive check + reactive backstop).

## From a mapping

```python
config = RuntimeConfig.from_mapping(
    {"model": model, "auto_compact_threshold": 0.75}
)
```

An invalid threshold is rejected fast at assembly:

```python
RuntimeConfig.from_mapping({"model": model, "auto_compact_threshold": 1.5})
# -> ConfigError: auto_compact_threshold must be a number in (0, 1]
```

## What it does (and does not) change

- **Reuses** the existing mechanical compaction (`compact_history`) — the same
  `SummaryMarkerBlock` digest, no new algorithm.
- **Reuses** the existing size heuristic (text chars ÷ 4, plus a fixed cost per
  non-text block) — no tokenizer, no new dependency. The estimate is a
  safety-margin trigger; the **reactive overflow path stays the backstop** if the
  estimate ever under-counts.
- **No event** is emitted by compaction (proactive or reactive) — it mutates
  in-memory history only; the durable stream keeps the originals. No event-schema
  or content-model change.
- The agent loop's turn cycle is unchanged; the only new behavior is the
  configurable pre-send trigger.

## Cheap-model summarizer (deferred)

Summarizing the compacted span with a cheap model (instead of the mechanical
digest) is a documented follow-on (**spec 042**) — see research.md Decision 3. It
is intentionally **not** part of this unit, which ships the configurable threshold
over the mechanical digest.
