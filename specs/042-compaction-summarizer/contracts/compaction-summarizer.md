# Contract: Optional Cheap-Model Compaction Summarizer

Behavioral contracts for the optional summarizer. All are verifiable offline with
a `ScriptedModel` (and `ScriptedFailure` / `ScriptedOverflow`) as the summarizer.

## C1 — A supplied summarizer writes the marker's summary

**Given** `RuntimeConfig.compaction_summarizer` is set to a `ModelBoundary` and a
compaction is triggered (proactive or reactive), **when** compaction runs,
**then** the resulting `SummaryMarkerBlock` in history carries the **model's**
summary text in its `SummaryDigest.excerpts`, while `turn_count` and `tool_names`
remain the mechanical values.

> Note: the mechanical `compact_history` runs first and composes the request; the
> overlay then augments the marker and the loop recomposes so the model sees the
> summarized marker.

## C2 — The summarizer receives the dropped span and no tools

**Given** a summarizer is set, **when** it is asked to summarize, **then** it
receives a `ModelRequest` whose `context` contains the **dropped** turns (the span
being compacted) plus a concise summarize instruction, and whose `tools` is empty.

## C3 — Default `None` is byte-identical to today

**Given** `compaction_summarizer = None` (the default), **when** compaction runs,
**then** the produced `SummaryMarkerBlock` equals the pre-042 mechanical digest
(same `turn_count`, `tool_names`, `excerpts`) and **no** model call is made for
summarization.

## C4 — FAIL-SAFE: a raising summarizer falls back to the mechanical digest

**Given** a summarizer that raises an exception, **when** compaction runs,
**then** the mechanical `SummaryMarkerBlock` stands (its `excerpts` are the
mechanical fragments, not a model summary) and the run completes **without** an
`unrecoverable-error` caused by the summarizer.

## C5 — FAIL-SAFE: empty output falls back to the mechanical digest

**Given** a summarizer that returns empty or whitespace-only text, **when**
compaction runs, **then** the mechanical digest is kept (empty is not a valid
summary).

## C6 — FAIL-SAFE: a timeout falls back to the mechanical digest

**Given** a summarizer that does not produce its turn within the guard timeout,
**when** compaction runs, **then** the summarize attempt is abandoned, the
mechanical digest is kept, and the run continues.

## C7 — No recursion / `ContextOverflowError` is a failure

**Given** a summarizer that signals `ContextOverflowError`, **when** compaction
runs, **then** it is treated like any failure (mechanical digest kept); the
summarizer is summarized with **no** assembler, **no** tools, and is **never**
retried by compacting again.

## C8 — `compact_history` and the content model are unchanged

The proactive and reactive paths invoke the **existing** `compact_history`
unchanged; the summary reuses the **existing** `SummaryMarkerBlock` /
`SummaryDigest` (no new block, no new field). No runtime event is emitted, no
`SCHEMA_VERSION` bump, no new public `__all__` name (the 014 api-reference
bijection stays green with no doc edit).

## C9 — Config round-trip & no-secret

`RuntimeConfig.compaction_summarizer` passes through `from_mapping` unchanged (an
object collaborator, like `model`); it is not a secret field (no
`api_key`/`token`/`secret`/`password`/`credential` on `RuntimeConfig`).
