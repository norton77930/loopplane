# Tasks: Cluster Fair Turn

**Input**: Design documents from `specs/086-cluster-fair-turn/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/cluster-fair-turn.md),
[ADR 0021](../../docs/adr/0021-cluster-fair-turn.md)

**Tests**: required (Constitution X). Every phase carries tests. Write the focused RED
check first; it must fail before the matching implementation.

## 🚦 Gate — nothing below may start yet

- [x] **T000** **ADR 0021 accepted by the maintainer** on 2026-09-03, before implementation
      began (spec FR-018; R2). The ADR status line reads `Accepted`. Gate discharged.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency
- **[Story]**: the user story from spec.md the task serves

---

## Phase 1: Setup

**Purpose**: confirm packaging and boundary constraints before code exists.

- [x] **T001** Confirm `pyproject.toml` extras / required deps are unchanged (FR-012). No
      new extra; optional Postgres rides `loopplane[postgres]`. Pin by leaving
      `tests/contract/test_packaging.py` green at the end.

---

## Phase 2: Foundational seams (blocks every story)

**Purpose**: permit Protocol, in-memory store, optional `turn_permits=` on
`PlatformFairness`, default-off constructor.

- [x] **T002** Add `TurnPermit` and `TurnPermitStore` Protocol to
      `src/loopplane/fairness.py` per [data-model.md](data-model.md) (`take` /
      `heartbeat` / `release`). Phase-1 MUST NOT import `loopplane.webapi`.
- [x] **T003** [P] Focused RED — `tests/unit/test_cluster_fair_turn.py`: import the new
      names; `PlatformFairness(policy)` still constructs without `turn_permits`.
- [x] **T004** Add `InMemoryTurnPermitStore` in `src/loopplane/fairness.py` — process
      lock, prune expired, count live permits against `active_cap`, fair next start
      against `consecutive_cap`, insert permit.
- [x] **T005** Add optional `turn_permits: TurnPermitStore | None = None` to
      `PlatformFairness.__init__` in `src/loopplane/fairness.py`. Default `None` is
      today's 072 object (keyword-only).
- [x] **T006** Wire `model_turn` in `src/loopplane/fairness.py` so a granted local 072
      turn then takes a cluster permit when `turn_permits` is set; store errors
      **degrade** to local-only (no hang, no new exception for the run).
- [x] **T007** [P] Test — `repr`/`str` of the in-memory store and a fairness object
      with a store never echo permit ids, holder ids, or principal dumps
      (`tests/unit/test_cluster_fair_turn.py`).

**Checkpoint**: seams exist; unused. Existing 072 suite still passes.

---

## Phase 3: User Story 1 — Two admitted principals both make progress (P1) 🎯 MVP

**Goal**: two simulated workers sharing one store; a burst of starts gives both
ready principals at least one start.

**Independent Test**: two `PlatformFairness` instances, one `InMemoryTurnPermitStore`,
`max_active_model_calls=1`, `max_consecutive_starts=1`. Interleave `model_turn` for
alice and bob; both obtain a start. Alice-only successive turns are not blocked.

- [x] **T008** [P] [US1] Focused RED — two fairness objects, one store, both principals
      ready: a burst of starts yields both at least one start
      (`tests/unit/test_cluster_fair_turn.py`).
- [x] **T009** [US1] Implement store take/fair-next so T008 passes.
- [x] **T010** [P] [US1] Test — only alice is ready: successive `model_turn` calls
      succeed (no wait for an absent peer) (`tests/unit/test_cluster_fair_turn.py`).

**Checkpoint**: US1 demonstrable at the fairness seam.

---

## Phase 4: User Story 2 — Default off is byte-identical (P1)

**Goal**: no `turn_permits` → existing 072 tests unchanged.

**Independent Test**: `tests/unit/test_platform_fairness.py` still green; constructing
`PlatformFairness(policy)` does not require the new argument.

- [x] **T011** [P] [US2] Run `tests/unit/test_platform_fairness.py` — no edits required
      if T005 default is `None`.
- [x] **T012** [P] [US2] Test — `PlatformFairness(policy)` identity: existing admit /
      consecutive-start behaviour in `tests/unit/test_platform_fairness.py` still holds
      with no collaborator.

**Checkpoint**: US2.

---

## Phase 5: User Story 3 — 085 admission is unchanged (P1)

**Goal**: cluster turn permits do not loosen or steal 085 grants.

**Independent Test**: overlapping POST /runs for one principal across two apps still
409 when admission is on, even if both hosts have `turn_permits` configured.

- [x] **T013** [P] [US3] Test — `tests/unit/test_webapi_admission.py`: two TestClients
      sharing an admission store; hosts built with `PlatformFairness(..., turn_permits=store)`;
      overlapping POST /runs still 409 `a run is already active`.

**Checkpoint**: US3.

---

## Phase 6: User Story 4 — Concurrent turns up to the 072 bound (P1)

**Goal**: no global single-flight lock unless `max_active_model_calls` is 1.

**Independent Test**: `max_active_model_calls=2` on the shared store; alice and bob
both enter `model_turn` at the same time.

- [x] **T014** [P] [US4] Test — two fairness objects, one store, `max_active_model_calls=2`:
      overlapping `model_turn("alice")` and `model_turn("bob")` both enter
      (`tests/unit/test_cluster_fair_turn.py`).
- [x] **T015** [P] [US4] Test — `max_active_model_calls=1`: bob waits until alice
      releases; bob does not steal alice's live permit
      (`tests/unit/test_cluster_fair_turn.py`).

**Checkpoint**: US4.

---

## Phase 7: User Story 5 — Control-plane outage does not wedge (P2)

**Goal**: store failure during `model_turn` degrades to local 072; the run proceeds.

**Independent Test**: `turn_permits.take` raises; `async with fairness.model_turn("alice")`
still enters; no hang.

- [x] **T016** [P] [US5] Test — boom store: `model_turn` still grants locally
      (`tests/unit/test_cluster_fair_turn.py`).
- [x] **T017** [P] [US5] Test — tiny TTL without heartbeat: after expiry another worker
      can take; live heartbeating holder is not overwritten
      (`tests/unit/test_cluster_fair_turn.py`).
- [x] **T018** [US5] Test — released permit cannot be heartbeated back into existence
      (`tests/unit/test_cluster_fair_turn.py`).

**Checkpoint**: US5.

---

## Phase 8: Optional Postgres + fail-degrade (not fail-closed)

**Purpose**: multi-worker production honesty; missing extra / store errors degrade.

- [x] **T019** Create `src/loopplane/fairness_postgres.py` (or a lazy helper next to
      fairness) — `PostgresTurnPermitStore`, lazy psycopg, `anyio.to_thread`, ADR 0008,
      DSN never echoed, schema once at construct, no File/SQLite backend. Fairness.py
      MUST NOT import this module at top level.
- [x] **T020** [P] Export the Postgres helper only if it is a public name; otherwise
      keep it importable as `loopplane.fairness_postgres` and document in
      `docs/api-reference.md` only if exported from `loopplane.fairness`.
- [x] **T021** [P] Offline Postgres tests via a stub in `tests/fairness_pg_stub.py`
      (085/060 pattern): take/release; missing extra raises a public-safe install
      message without leaking a DSN (`tests/unit/test_cluster_fair_turn.py`).
- [x] **T022** Confirm `src/loopplane/loop/loop.py` and `src/loopplane/webapi/app.py`
      are unchanged (ADR 0021 D3 / D8).

**Checkpoint**: optional durable path; no create_app / loop wiring.

---

## Phase 9: Polish, docs, gates

- [x] **T023** [P] `docs/api-reference.md` — `PlatformFairness` constructor note and any
      new public names; bijection stays green.
- [x] **T024** [P] `CHANGELOG.md` `[Unreleased]` — unit 086.
- [x] **T025** [P] `docs/capabilities.md` and `docs/gap-analysis.md` — G20 remaining is
      weighted tiers + live migration; record the 086 fair-turn slice.
- [x] **T026** Confirm [quickstart.md](quickstart.md) matches the shipped constructor
      (`turn_permits=`, no `create_app` argument).
- [x] **T027** Four gates through PowerShell: `ruff format --check`, `ruff check`,
      `mypy src`, `pytest`. Never two pytest processes. Reconcile new tests against
      the current baseline rather than hiding skips.
- [x] **T028** Public-safety scan over changed and untracked files
      (`tests/contract/test_public_safety.py` pattern).
- [x] **T029** `uv lock --check` (pyproject should be unchanged).
- [x] **T030** Update `docs/loopplane-agent-board.md` §3/§4 to **Implemented** (not
      Verified — FR-019 code + architecture review is the maintainer's follow-up).
- [x] **T031** Final review: no Event Bus/schema/Gateway/`_active`/new extra/default/
      `create_app` signature change; 061/072/085 tests still pass with `turn_permits`
      absent.
- [x] **T032** Code-review remediations: `hold_turn` CM, shared `schedule()` for
      in-memory and Postgres, degrade only on `TurnPermitUnavailable`. FR-019
      architecture-reviewer GO, 0 blocking. Board §3/§4 → **Verified**.

---

## Dependencies

```text
T000 (ADR accepted)
  └─ Phase 1 (T001)
       └─ Phase 2 seams (T002–T007) ── blocks every story
            ├─ US1 (T008–T010) ── US2 (T011–T012) ── US3 (T013) ── US4 (T014–T015)
            ├─ US5 (T016–T018)
            └─ Phase 8 Postgres (T019–T022)
                 └─ Phase 9 polish (T023–T031)
```

## Parallel opportunities

Test tasks marked [P] that touch only `tests/unit/test_cluster_fair_turn.py` still
serialize with each other. Genuine parallel: docs T023–T025 vs Postgres T019.

## MVP

T000 + Phase 2 + US1 (T008–T010) + US2 (T011–T012) is the smallest demonstrable
slice. This unit ships all stories before review.

## Independent tests (per story)

| Story | How to verify alone |
| ----- | ------------------- |
| US1 | Two `PlatformFairness` + one store; both principals get a start |
| US2 | `tests/unit/test_platform_fairness.py` green with no collaborator |
| US3 | Admission 409 still holds with `turn_permits` on the hosts |
| US4 | `max_active_model_calls=2` overlapping enters; `=1` waits without steal |
| US5 | Boom store still grants local `model_turn` |
