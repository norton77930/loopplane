# Tasks: Distributed Host Pool

**Input**: Design documents from `specs/085-distributed-host-pool/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/distributed-host-pool.md),
[ADR 0020](../../docs/adr/0020-distributed-host-pool.md)

**Tests**: required (Constitution X). Every phase carries tests. Write the focused RED
check first; it must fail before the matching implementation.

## 🚦 Gate — nothing below may start yet

- [x] **T000** **ADR 0020 accepted by the maintainer** on 2026-09-02, before implementation
      began (spec FR-020; R2). The ADR status line reads `Accepted`. Gate discharged.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency
- **[Story]**: the user story from spec.md the task serves

---

## Phase 1: Setup

**Purpose**: confirm the packaging and boundary constraints before code exists.

- [x] **T001** Confirm `pyproject.toml` extras / required deps are unchanged (FR-014). No
      new extra; Postgres rides `loopplane[postgres]`. Pin by leaving
      `tests/contract/test_packaging.py` green at the end.

---

## Phase 2: Foundational seams (blocks every story)

**Purpose**: Protocol, in-memory store, coordinator `hold()`, public-safe reject type.

- [x] **T002** Create `src/loopplane/webapi/admission.py` with `AdmissionGrant`,
      `AdmissionRejected(kind: conflict|capacity)`, and `AdmissionStore` Protocol per
      [data-model.md](data-model.md). Types + `AdmissionRejected` messages equal the
      existing HTTP phrases.
- [x] **T003** [P] Focused RED — `tests/unit/test_webapi_admission.py`: import the new
      names; `AdmissionRejected("conflict")` string is `a run is already active`;
      `capacity` is `capacity exceeded`.
- [x] **T004** Add `InMemoryAdmissionStore` in `src/loopplane/webapi/admission.py` —
      per-principal lock, prune expired, count in-flight/outstanding, insert grant.
- [x] **T005** Add `AdmissionCoordinator.hold` in the same module — take, heartbeat
      nursery at `ttl/3`, release in `finally`. Caps are constructor args
      (`in_flight_cap`, `outstanding_cap=None`). `holder_id` opaque uuid default.
- [x] **T006** Add `bound_run(admission, pool, principal_id)` context manager: cluster
      `hold` then local `pool.in_flight` (either side no-op when None).
- [x] **T007** Export `AdmissionCoordinator`, `AdmissionGrant`, `AdmissionRejected`,
      `AdmissionStore`, `InMemoryAdmissionStore`, `bound_run` from
      `src/loopplane/webapi/__init__.py`.
- [x] **T008** [P] Test — `repr`/`str` of the in-memory store and coordinator never
      include grant ids or principal lists that look like a dump (FR-009).

**Checkpoint**: seams exist; unused. Existing suite still passes.

---

## Phase 3: User Story 1 — One principal, two workers, still sequential (P1) 🎯 MVP

**Goal**: two simulated workers sharing one store; second overlapping hold rejects.

**Independent Test**: `async with worker_a.hold("alice")` then `worker_b.hold("alice")`
raises `AdmissionRejected(kind="conflict")`; after exit, worker_b succeeds.

- [x] **T009** [P] [US1] Focused RED — two coordinators, one `InMemoryAdmissionStore`,
      same principal, in_flight_cap=1: overlapping hold rejects; sequential holds
      succeed (`tests/unit/test_webapi_admission.py`).
- [x] **T010** [US1] Implement take/reject/release so T009 passes.

**Checkpoint**: US1 demonstrable at the store/coordinator seam.

---

## Phase 4: User Story 2 — Two principals still concurrent (P1)

**Goal**: Alice on worker 1 and Bob on worker 2 both proceed.

**Independent Test**: overlapping holds for two principals both enter.

- [x] **T011** [P] [US2] Focused RED then green — overlapping `hold("alice")` and
      `hold("bob")` both succeed (`tests/unit/test_webapi_admission.py`).

**Checkpoint**: US1 + US2.

---

## Phase 5: User Story 3 — Caps are global (P1)

**Goal**: in-flight and outstanding caps are cluster-scoped, not per worker.

**Independent Test**: fill cap via worker 1; worker 2 reject; release then reuse.

- [x] **T012** [P] [US3] Test — in_flight_cap=1 filled on worker 1 → worker 2 conflict;
      after release either worker can take (`tests/unit/test_webapi_admission.py`).
- [x] **T013** [P] [US3] Test — outstanding_cap=1 filled → worker 2 `kind="capacity"`;
      fairness-off (`outstanding_cap=None`) does not apply that check.

**Checkpoint**: US3.

---

## Phase 6: User Story 4 — Default off is byte-identical (P1)

**Goal**: `create_app` without `admission` unchanged; existing 061/072 tests still pass.

**Independent Test**: POST /runs without admission still 200; pool-only in_flight still
409 on local overlap.

- [x] **T014** [US4] Add `admission: AdmissionCoordinator | None = None` to
      `create_app` in `src/loopplane/webapi/app.py` and `RouterState` in
      `src/loopplane/webapi/routers/context.py`. Default None.
- [x] **T015** [US4] Wrap `POST /runs` in `src/loopplane/webapi/routers/interaction.py`
      with `bound_run`; catch `AdmissionRejected` **before** `RuntimeError` → 409/429.
- [x] **T016** [P] [US4] Test — `create_app` without admission: existing pool routing
      test still 200 (`tests/unit/test_tenant_host_pool.py` unchanged behaviour).
- [x] **T017** [P] [US4] Test — two TestClients sharing one store: second overlapping
      POST /runs for the same principal is 409 `a run is already active`
      (`tests/unit/test_webapi_admission.py`).

**Checkpoint**: HTTP path for US1+US4.

---

## Phase 7: User Story 5 — Dead worker does not pin forever (P2)

**Goal**: TTL expiry allows a later take; a live heartbeating holder is not overwritten.

**Independent Test**: short TTL, no heartbeat → next take succeeds; with heartbeat →
second take still conflict.

- [x] **T018** [P] [US5] Test — grant with tiny TTL and no heartbeat: after expiry the
      next take succeeds (`tests/unit/test_webapi_admission.py`).
- [x] **T019** [P] [US5] Test — live `hold()` with heartbeat: overlapping take still
      conflict while the first `async with` is entered (`tests/unit/test_webapi_admission.py`).
- [x] **T020** [US5] Test — released grant cannot be heartbeated back into existence
      (`heartbeat` returns False; take by another holder succeeds).

**Checkpoint**: US5.

---

## Phase 8: User Story 6 — Many-writer ownership (P2)

**Goal**: concurrent takes: exactly one winner; stale write cannot resurrect.

**Independent Test**: two tasks start `hold` together; one `AdmissionRejected`; one
success.

- [x] **T021** [P] [US6] Test — concurrent overlapping takes on one store: exactly one
      success (`tests/unit/test_webapi_admission.py`).
- [x] **T022** [P] [US6] Test — after release, a heartbeat for the old grant_id returns
      False and does not recreate the row.

**Checkpoint**: US6 at the in-memory store.

---

## Phase 9: All run-start paths + Postgres + fail-closed

**Purpose**: ADR 0020 D8 wrap; optional Postgres backend; store errors fail closed.

- [x] **T023** [US1] Wrap `run_event_stream` drive in `src/loopplane/webapi/streaming.py`
      with `bound_run`; map `AdmissionRejected` to the existing SSE error phrases.
- [x] **T024** [US1] Wrap `run_session` in `src/loopplane/webapi/sessions.py` with
      `bound_run`; `open_session` maps conflict→409 and capacity→429.
- [x] **T025** [P] [US1] Test — POST /runs/events overlapping the same principal across
      two apps sharing a store → 409 error frame (or HTTP 409 if mapped before stream).
- [x] **T026** Create `src/loopplane/webapi/admission_postgres.py` —
      `PostgresAdmissionStore`, lazy psycopg, `anyio.to_thread`, ADR 0008, DSN never
      echoed, `SELECT … FOR UPDATE` take, no File/SQLite backend.
- [x] **T027** [P] Export `PostgresAdmissionStore` from `src/loopplane/webapi/__init__.py`.
- [x] **T028** [P] Offline Postgres tests via a dedicated SQL stub
      `tests/admission_pg_stub.py` (060/062 pattern): concurrent take exactly one
      winner; release; missing extra raises a public-safe install message.
- [x] **T029** [P] Test — store `.take` raising becomes `AdmissionRejected` (fail-closed);
      no uncoordinated fallback (`tests/unit/test_webapi_admission.py`).

**Checkpoint**: all drive paths + Postgres optional path.

---

## Phase 10: Polish, docs, gates

- [x] **T030** [P] `docs/api-reference.md` — new public names; bijection stays green.
- [x] **T031** [P] `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` §3 additive
      sentence (ADR 0020 D9): webapi owns optional cross-process admission leases;
      they are not session state (G3).
- [x] **T032** [P] `CHANGELOG.md` `[Unreleased]` — unit 085.
- [x] **T033** [P] `docs/capabilities.md` and `docs/gap-analysis.md` — G20 still partial
      (cluster turn interleaving deferred); record the 085 ownership/admission slice.
- [x] **T034** [P] `docs/web-api-host.md` — opt-in `admission=` and 409/429 phrases.
- [x] **T035** Rollback path already in ADR 0020 + quickstart (FR-019); confirm
      [quickstart.md](quickstart.md) matches the shipped constructors.
- [x] **T036** Four gates through PowerShell: `ruff format --check`, `ruff check`,
      `mypy src`, `pytest`. Never two pytest processes. Reconcile new tests against
      the current baseline rather than hiding skips.
- [x] **T037** Public-safety scan over changed and untracked files
      (`tests/contract/test_public_safety.py` pattern).
- [x] **T038** `uv lock --check` (pyproject should be unchanged).
- [x] **T039** Update `docs/loopplane-agent-board.md` §3/§4 to **Implemented** (not
      Verified — FR-021 code + architecture review is the maintainer's follow-up).
- [x] **T040** Final review: no Event Bus/schema/Gateway/`_active`/new extra/default
      change; 061/072 tests still pass with admission absent.
- [x] **T041** G5 remediation: `bound_run(..., hold_local=)` so `admission=None` does
      not expand 061 `in_flight` onto streaming/session (ADR D3/D8). FR-021
      code-reviewer passed; architecture-reviewer second pass GO, 0 blocking.
      Board §3/§4 → **Verified**.

---

## Dependencies

```text
T000 (ADR accepted)
  └─ Phase 1 (T001)
       └─ Phase 2 seams (T002–T008) ── blocks every story
            ├─ US1 (T009–T010) ── US2 (T011) ── US3 (T012–T013)
            ├─ US4 wiring (T014–T017)
            ├─ US5 (T018–T020)
            ├─ US6 (T021–T022)
            └─ Phase 9 paths + Postgres (T023–T029)
                 └─ Phase 10 polish (T030–T040)
```

## Parallel opportunities

Test tasks marked [P] that touch only `tests/unit/test_webapi_admission.py` still
serialize with each other. Genuine parallel: docs T030–T034 vs Postgres T026.

## MVP

T000 + Phase 2 + US1 (T009–T010) + US4 HTTP wrap (T014–T017) is the smallest
demonstrable slice. This unit ships all stories before review.
