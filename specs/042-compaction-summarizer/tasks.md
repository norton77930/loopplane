# Tasks: Optional Cheap-Model Compaction Summarizer

**Feature**: `specs/042-compaction-summarizer` | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

Additive, reuse-first, FAIL-SAFE. TDD: the failing offline tests come first
(T001), then the implementation (T002–T008), then verification + tracking
(T009–T011). All deterministic; no live calls.

- [x] **T001** — `tests/unit/test_compaction_summarizer.py` (NEW, offline, written
  FIRST and failing): a `ScriptedModel` as the summarizer + a request-recording
  wrapper. Cover Contracts C1–C9:
  - C1: a set summarizer puts its scripted summary into the marker's
    `SummaryDigest.excerpts`; `turn_count` / `tool_names` stay mechanical.
  - C2/C4 (US1/SC-004): the summarizer receives a `ModelRequest` whose context
    carries the dropped turns and whose `tools` is empty.
  - C3 (US2): `compaction_summarizer=None` → the mechanical digest, byte-identical
    to the pre-042 marker, and the summarizer is never consulted.
  - C4/C5/C6/C7 (US3, the FAIL-SAFE cases): a raising summarizer, an empty-output
    summarizer, a timing-out summarizer, and a `ContextOverflowError` summarizer
    each fall back to the mechanical digest and the run still terminates normally
    (no summarizer-caused `unrecoverable-error`).
  - direct unit test of `summarize_compaction(...)`: success → model summary in
    the digest; raise/empty/overflow → the unchanged mechanical marker.
  - C9: `RuntimeConfig.from_mapping` round-trips `compaction_summarizer`; it is not
    a secret field.

- [x] **T002** — `src/loopplane/loop/history.py`: add
  `replace_entry(self, index: int, entry: HistoryEntry) -> None` — a tiny additive
  in-memory swap mirroring `replace_prefix` (does **not** invoke the recording
  hook; the durable stream keeps the originals). (FR-003/FR-010.)

- [x] **T003** — `src/loopplane/loop/summarizer.py` (NEW, internal, **no
  `__all__`**): `async def summarize_compaction(*, summarizer, dropped, marker,
  timeout_seconds=...) -> SummaryMarkerBlock`. Build `ModelRequest(context=
  [instruction, *messages_from(dropped)], tools=[])`; collect `TextIncrement.text`
  under `anyio.fail_after(timeout_seconds)`; on success (non-empty, non-whitespace)
  return a marker with the summary in `excerpts` (keeping `turn_count` /
  `tool_names`); on **ANY** failure (exception incl. `ContextOverflowError`,
  `TimeoutError`, empty output) return `marker` unchanged. **Never raises.**
  (FR-003/FR-004/FR-005/FR-006/FR-007.)

- [x] **T004** — `src/loopplane/loop/assembly.py`: add a one-shot
  `_just_compacted` flag + `take_compacted(self) -> bool` (read-and-clear), set
  `True` when the proactive branch's `compact_history(...)` returns `True`. Mirrors
  `mark_compacted` / `_needs_reestablish`. `compact_history` / `_estimate_tokens`
  reuse unchanged. (FR-008/FR-010.)

- [x] **T005** — `src/loopplane/loop/loop.py`: `AgentLoop.__init__` gains
  `summarizer: ModelBoundary | None = None`. In the assemble/turn loop: capture the
  pre-compaction history snapshot, call `self._assemble(prompt)`; if a summarizer
  is set and the assembler reports `take_compacted()`, run the overlay over the
  dropped span and recompose the request so the model sees the summarized marker.
  In `except ContextOverflowError`: after the existing `compact_history(...)`
  returns `True`, run the overlay over the captured dropped span before the retry.
  One additive awaited step each — the turn cycle is preserved. (FR-003/FR-005/
  FR-010.)

- [x] **T006** — `src/loopplane/controller/controller.py`: `RuntimeController.
  __init__` gains `compaction_summarizer: ModelBoundary | None = None`; store it;
  pass it to the per-session `AgentLoop(summarizer=self._compaction_summarizer)` in
  `_assemble`. (FR-009.)

- [x] **T007** — `src/loopplane/host/config.py`: add `compaction_summarizer:
  ModelBoundary | None = None` to `RuntimeConfig`; `from_mapping` pass-through
  (`data.get("compaction_summarizer")`, object collaborator — no coercion). **No**
  new `validate_config` rule (any `ModelBoundary` is valid; `None` is off). No new
  `__all__` name. (FR-001/FR-009/FR-012.)

- [x] **T008** — `src/loopplane/host/assembly.py`: thread
  `config.compaction_summarizer` into the `RuntimeController(...)` kwargs (when not
  `None`), mirroring `auto_compact_threshold`. (FR-009.)

- [x] **T009** — Run the four gates green and iterate: `uv run ruff check .`;
  `uv run ruff format .` then `uv run ruff format --check .`; `uv run mypy`
  (src-only, strict → "Success"); `uv run pytest -q` (the prior baseline + the new
  tests). (SC-005.)

- [x] **T010** — Tracking: `.specify/feature.json` →
  `specs\\042-compaction-summarizer`; `CLAUDE.md` SPECKIT block →
  `specs/042-compaction-summarizer/plan.md`; `CHANGELOG.md` a `- **042**` entry in
  `[0.2.0]`'s `### Added` (keep `test_changelog.py` green); `docs/loopplane-agent-board.md`
  a `042-compaction-summarizer` §3 row + §4 update.

- [x] **T011** — Final review: confirm default-`None` is byte-identical, the loop /
  events / content model are untouched (only the additive overlay + wiring), and
  no `__all__`/api-reference change is needed (the 014 bijection stays green).

## Dependencies

- T001 (failing tests) precedes the implementation (TDD).
- T002 (`replace_entry`) and T003 (`summarize_compaction`) are foundational; T005
  (loop wiring) depends on both. T004 (assembler flag) is needed by T005's
  proactive path. T006–T008 thread the config (each depends on the prior layer's
  signature). T009 verifies; T010/T011 track.

## Rollback (Constitution X)

`compaction_summarizer = None` (the default) → byte-identical to pre-042. Full
revert: drop `loop/summarizer.py`, the `replace_entry` helper, the assembler flag,
the loop's two overlay calls + `summarizer` param, and the controller/config/host
wiring → the exact pre-042 mechanical compaction.
