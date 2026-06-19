# Tasks: Configurable Proactive Auto-Compaction

**Feature**: `041-auto-compaction` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Dependency-ordered, TDD-first (Constitution X). `[P]` = parallelizable.
All tests are deterministic and offline.

## Phase 1 — Failing tests first (TDD)

- [x] **T001** — `tests/unit/test_auto_compaction.py` (NEW): write failing tests for
  `PromptAssembler` proactive sizing — (a) `_effective_capacity`: `None` → full
  capacity; `1.0` → capacity; `0.5`/`1000` → `500`; (b) ON: a threshold + an
  oversized history → the assembled request carries a `SummaryMarkerBlock` (driven
  through a `RuntimeController` + `RecordingModel`, asserting the request the model
  received was already compacted, with no overflow); (c) ON: a sub-threshold
  history → no `SummaryMarkerBlock`. (Contracts C1, C2, C4.)
- [x] **T002** — In `tests/unit/test_auto_compaction.py`, add failing tests for the
  default-`None` byte-identity: with `auto_compact_threshold=None`, a sub-full
  history is **not** compacted (identical to today) and an over-full history **is**
  still compacted (the existing full-capacity trigger preserved). (Contract C3.)
- [x] **T003** [P] — In `tests/unit/test_auto_compaction.py`, add a failing test
  that the reactive `ContextOverflowError` backstop is unchanged with a threshold
  set: one overflow → compact + retry once → `natural-completion`; two overflows →
  `unrecoverable-error`. (Contract C5.)
- [x] **T004** [P] — In `tests/unit/test_auto_compaction.py`, add failing config
  tests: `RuntimeConfig.from_mapping` round-trips `auto_compact_threshold`
  (coerced to `float`; absent → `None`); an invalid value (`0`, negative, `1.5`,
  `NaN`) raises `ConfigError` at `LoopPlaneHost`/`validate_config`; the no-secret
  config contract still holds. (Contracts C7, C8.)

## Phase 2 — Implementation (make the tests pass)

- [x] **T005** — `src/loopplane/loop/assembly.py`: add `compact_threshold: float |
  None = None` to `PromptAssembler.__init__` (store as `self._compact_threshold`);
  add `_effective_capacity(capacity)` (full capacity when `None`, else
  `int(capacity * threshold)`); change the proactive check in `assemble` to compare
  the estimate against `_effective_capacity(capacity)`. `_estimate_tokens` /
  `compact_history` reuse unchanged. (FR-002/003/004/006.)
- [x] **T006** — `src/loopplane/controller/controller.py`: add
  `auto_compact_threshold: float | None = None` to `RuntimeController.__init__`
  (store as `self._auto_compact_threshold`); pass it to the per-session
  `PromptAssembler(compact_threshold=self._auto_compact_threshold)` in `_assemble`.
  (FR-008.)
- [x] **T007** — `src/loopplane/host/config.py`: add `auto_compact_threshold: float
  | None = None` to `RuntimeConfig` (document inline); coerce it in `from_mapping`
  (to `float` or `None`); validate it in `validate_config` (raise `ConfigError`
  unless `None` or a finite number in `(0, 1]`). (FR-001/005/008.)
- [x] **T008** — `src/loopplane/host/assembly.py`: thread
  `config.auto_compact_threshold` into the `RuntimeController(...)` kwargs (added
  only when not `None`, matching the existing optional-kwarg pattern). (FR-008.)

## Phase 3 — Docs & tracking

- [x] **T009** [P] — Usage documentation: the feature `quickstart.md` is the usage
  guide (default-off, the threshold, reuse + the reactive backstop, the deferred
  summarizer), matching the 038/040 precedent (those Tier-2/Tier-3 config units
  added no standalone `docs/*.md`). No `docs/*.md` is added, so the unit-014 docs
  index contract (`tests/contract/test_docs_examples_index.py`) stays green with no
  edit. (Docs.)
- [x] **T010** [P] — `CHANGELOG.md`: add a `- **041** ...` entry after `- **040**
  ...`.
- [x] **T011** [P] — `docs/loopplane-agent-board.md`: add a `041-auto-compaction`
  §3 row after the `040` row + update §4 (041 done; the remaining Tier-3 follow-on
  is the cheap-model summarizer (spec 042, deferred); other untouched tiers noted).
- [x] **T012** [P] — `.specify/feature.json` → `specs\\041-auto-compaction`;
  `CLAUDE.md` SPECKIT block → `specs/041-auto-compaction/plan.md`.

## Phase 4 — Gates (all green via the locked toolchain)

- [x] **T013** — `uv run ruff check .`
- [x] **T014** — `uv run ruff format .` then `uv run ruff format --check .`
- [x] **T015** — `uv run mypy` (src-only, strict → "Success")
- [x] **T016** — `uv run pytest -q` (prior 919 passed + the new auto-compaction
  tests; no existing test needs updating — the default-`None` path is
  byte-identical, proven by T002).

## Notes

- **No api-reference edit** (FR-011): no new public package/`__all__` name
  (`auto_compact_threshold` is a field on the existing `RuntimeConfig`; the
  assembler/controller gain only constructor parameters; `_effective_capacity` is
  a private method), so the unit-014 bijection
  (`tests/contract/test_api_reference.py`) stays green untouched.
- **No event-schema change** (FR-010): compaction is silent today and stays
  silent; no `SCHEMA_VERSION` bump (Constitution VI).
- **Cheap-model summarizer deferred** (FR-012): documented as spec 042 in
  research.md Decision 3 — not implemented here.
- **Rollback** (Constitution X): `auto_compact_threshold = None`, or revert the
  assembler/controller/config additions → exact pre-threshold behavior.
