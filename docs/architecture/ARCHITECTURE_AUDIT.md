# LoopPlane Architecture Audit (Frozen Snapshot)

> **Snapshot**: audited 2026-07-06 · commit `d095c8b` · read-only (no tests run, no files modified).
> **Evidence tags**: `[RO-VERIFIED]` confirmed by direct file reads/greps during the audit · `[INFERRED]` reasonable inference · `[UNVERIFIED]` taken from recorded documentation, not re-verified.
> **Maintenance rule**: this file is a point-in-time snapshot; it does not self-update. Re-run the audit and refresh the snapshot header every ~10 units or before each release. Before relying on this file, confirm the tree has not moved substantially past the snapshot commit.

## 1. Source-of-truth decision

Trust ladder (higher wins on conflict):

1. `src/loopplane/**`, `tests/**`, `pyproject.toml`, `apps/web`, `apps/desktop` — ultimate facts `[RO-VERIFIED]`
2. `docs/loopplane-agent-board.md` — the single authority on unit completion (001–075 Verified; 076–078 Not started) `[RO-VERIFIED]`
3. `docs/api-reference.md` — current through unit 072 `[RO-VERIFIED]`
4. `specs/064`–`specs/075` — design intent of the newest units (tasks.md fully checked) `[RO-VERIFIED]`
5. `docs/capabilities.md`, `docs/gap-analysis.md` — stop at unit 063 / v0.4.0, twelve units behind `[RO-VERIFIED]`
6. `CHANGELOG.md` — stops at [0.4.0] = unit 063 `[RO-VERIFIED]`

**Never use as completion-status sources:**

- `README.md` — frozen at the unit-013 era (layer map lists only 001–013; only the `web` extra is mentioned) `[RO-VERIFIED]`
- The `Status: Draft` field in `specs/*/spec.md` — unmaintained across all 75 units `[RO-VERIFIED]`
- Unchecked tasks.md boxes in older units — 27 older units (001, 015–039, 043) carry historical checkbox drift, reconciled by `docs/spec-task-audit-exceptions.md` + `tests/contract/test_spec_task_audit.py` `[RO-VERIFIED]`
- `openspec/` — gitignored private reference corpus (see `.gitignore`); must never be committed (Constitution II/VII) `[RO-VERIFIED]`

## 2. Current architecture map `[RO-VERIFIED]`

31 packages + 3 root modules (`context.py`, `errors.py`, `fairness.py`). The top-level `src/loopplane/__init__.py` holds only `__version__` with no re-exports; every subpackage except `adapters` defines `__all__`; `py.typed` + mypy strict.

- **Phase-1 core runtime**: `loop`, `model`, `gateway`, `events`, `context.py`, `errors.py`, `fairness.py`, `hooks`, `approval`, `budget`, `artifacts`, `checkpoint`, `memory`, `controller`
- **Phase-2 hosts**: `host` (`host/assembly.py::assemble` is the single composition root), `cli`, `webapi`, `studio`, `commands`
- **Phase-3 loop engineering**: `engineering` (`run_loop` is the only entry), `scheduling`, `packs`, `review`, `recall`, `orchestration`
- **Governance & tool ecosystem**: `governance`, `tools`, `adapters`, `toolkit`, `skills`, `plugins`, `inspect`, `observability`, `ledger`, `pricing`
- **Apps (non-Python)**: `apps/web` (Vite SPA), `apps/desktop` (Electron + sidecar)

Verified import-direction rules `[RO-VERIFIED]`:

- `orchestration` never imports `gateway`/`context`/`model` (grep: zero hits).
- `controller`/`engineering`/`loop` never import `tools`; `from loopplane.tools` appears only in `context.py` (TYPE_CHECKING-only) and `host/assembly.py` (lazy, inside functions).
- The neutral Protocols (`BackgroundSupervisor` / `ScheduleSupervisor` / `SwarmSupervisor` / `WorktreeManager`) live in `context.py`.
- `webapi` only embeds `LoopPlaneHost`; it never re-composes runtime internals.

## 3. Load-bearing files (inbound-import ranking) `[RO-VERIFIED]`

1. `src/loopplane/model/` (`boundary.py` + `content.py`) — imported by 48 files; highest blast radius
2. `src/loopplane/errors.py` + `gateway` + the `host` facade — 39 files
3. `src/loopplane/events/` (`envelope.py` + `emitter.py`; `SCHEMA_VERSION = 1`) — 23 files
4. `src/loopplane/context.py` — 18 files
5. `src/loopplane/host/assembly.py` — few importers, but the single wiring path

## 4. README / documentation staleness `[RO-VERIFIED]`

Three tiers of staleness at audit time: README (~unit 013) ≪ docs (capabilities/gap at 063, api-reference at 072) ≪ code (075).

- README lists only the `web` extra (pyproject defines 9), omits the `loopplane` console script, and brands the product a "control plane" while every other doc says "embeddable agent harness runtime". The README's failure mode is **omission, not fabrication**.
- `CHANGELOG.md` + `__version__` stop at 0.4.0 / unit 063; units 064–075 (with ADRs 0011–0014) are not in any released section.
- The `CLAUDE.md` SPECKIT pointer lagged at 067 while `AGENTS.md` correctly pointed at 075.

## 5. Test gaps

- Three-layer pattern: `unit/test_<pkg>_core` + `contract/test_<pkg>_boundary` + `integration/test_<pkg>_us*`; global `--timeout=60 --timeout-method=thread` `[RO-VERIFIED]`.
- Thin relative to size `[INFERRED]`: `engineering` (10 source files, one focused unit test), `controller` (no dedicated test file), `memory`, `skills`, `context.py`/`errors.py` (indirect coverage only).
- `examples/` covers only the ~001–024 era capabilities `[RO-VERIFIED]`.
- Known flakes (documented, not open failures): `tests/integration/test_examples_smoke.py` timeouts under full-suite load; `test_us2_mcp` CPU contention `[UNVERIFIED]` (from the board).

## 6. Not re-verified in this audit `[UNVERIFIED]`

- Test counts (board records: pytest 1378 passed / 8 skipped; apps/web 128 Vitest; desktop 10 Vitest) — not re-run.
- When `tests/live/` (real-model validation) last ran.
- Actual packaging state of `apps/desktop` (structure confirmed only).
