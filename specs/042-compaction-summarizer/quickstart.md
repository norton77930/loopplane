# Quickstart: Optional Cheap-Model Compaction Summarizer

Spec 042 adds an **optional** cheap-model summarizer to compaction. When you
supply a (typically cheap/fast) summarizer model, the runtime uses it to write a
readable summary of the conversation span that compaction drops, instead of the
mechanical excerpts. When you do not, compaction is exactly as before.

## Default (no summarizer) — unchanged

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig

# compaction_summarizer defaults to None: compaction produces the mechanical
# digest (turn count + tool names + excerpts), byte-identical to today.
host = LoopPlaneHost(RuntimeConfig(model=model))
```

## With a cheap summarizer

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig
# any ModelBoundary works as the summarizer — a cheap/fast model is ideal, e.g.:
# from loopplane.adapters.openai import openai_model
# summarizer = openai_model("gpt-5-mini")

host = LoopPlaneHost(
    RuntimeConfig(
        model=model,
        compaction_summarizer=summarizer,
        # often paired with proactive compaction (spec 041):
        auto_compact_threshold=0.8,
    )
)
```

When compaction runs (proactively at the threshold, or reactively on a context
overflow), the runtime asks `summarizer` to summarize the dropped turns and puts
that summary into the compaction marker. `turn_count` and `tool_names` stay
mechanical.

## From a mapping

```python
RuntimeConfig.from_mapping({"model": model, "compaction_summarizer": summarizer})
```

`compaction_summarizer` is an object collaborator (like `model`), so it passes
through `from_mapping` unchanged — no coercion, no validation rule.

## FAIL-SAFE behavior (the guarantee)

The summarizer is a pure overlay on top of the mechanical digest:

- The mechanical `compact_history` **always runs first** and produces a complete,
  valid compaction marker.
- The summarizer then *augments* that marker with a model-written summary.
- If the summarizer **errors, times out, signals context overflow, or returns
  empty output**, the augmentation is skipped and the **mechanical digest
  stands**. Compaction always succeeds; **a run is never broken because the
  summarizer failed.**
- The summarizer is a single, plain model turn — **no tools, no assembler, no
  compaction of its own** — so it cannot recurse.

## Notes

- **Reuses** the existing `SummaryMarkerBlock` / `SummaryDigest` — no new block,
  no new event, no `SCHEMA_VERSION` bump (the model summary replaces the digest's
  `excerpts`).
- **Carries no secret** — a summarizer's credential lives in the host-supplied
  model object, never in the config.
- **Default-off is byte-identical** — `compaction_summarizer = None` (or omitting
  it) restores the exact pre-042 mechanical compaction.
- A summarizer alone does not enable assembly; the proactive compaction path still
  requires the assembler (memory/skills configured, or `enable_assembly`), exactly
  as in spec 041. The reactive overflow path always applies.
