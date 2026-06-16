---
description: "Task list for unit 022 — Web Principal Authentication & Per-Principal Session Scoping"
---

# Tasks: Web Principal Authentication & Per-Principal Session Scoping

**Input**: Design documents from `specs/022-web-principal-auth/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Security-critical: write the two-principal scoping +
default-deny + no-leak tests FIRST and confirm they FAIL before implementing.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency**: FastAPI stays the existing `web` extra;
  `pyproject.toml` and the extras set are unchanged; `tests/contract/test_packaging.py`
  stays green without edits (verified in T014).

---

## Phase 2: Foundational (identity primitives + additive owner plumbing — block all stories)

- [ ] T002 `tests/integration/test_webapi_principal_scoping.py` (FAIL first): drive the
  FastAPI app with `token_authenticator({"tok-a":"alice","tok-b":"bob"})` — (US1) Alice
  opens/runs a session; Alice's `GET /v1/sessions` lists it; Bob's listing excludes it and
  Bob's `history/events/submit/resume/artifacts/cancel` on Alice's id returns **404**;
  (US3) `create_app(host)` with no authenticator → every route `401`; a raising verifier →
  `401`; no response/error body contains the credential or principal token.
- [ ] T003 `src/loopplane/webapi/auth.py`: add `Principal` (frozen, `id: str`); change
  `Authenticator` to `Callable[[str | None], Awaitable[Principal | None]]`; `DENY_ALL`
  returns `None`; add `token_authenticator(tokens: Mapping[str, str])` (Bearer→Principal);
  `make_auth_dependency` resolves a `Principal` (fixed `401`, no credential, on `None`/raise).
- [ ] T004 `src/loopplane/webapi/__init__.py`: export `Principal` and `token_authenticator`
  in `__all__`.
- [ ] T005 Additive, optional `principal_id` plumbing (all `str | None = None`, zero
  behavior change when unset): `SessionMetaPayload` (`checkpoint/records.py`),
  `SessionSummary` (`checkpoint/base.py`), `SessionRecorder` → writes it into the meta
  (`checkpoint/recorder.py`), `controller` `_Session` / `create_session` / `_assemble`
  + in-memory `list_sessions` summary (`controller/controller.py`), and `host.run` /
  `host.session` → `controller.create_session(principal_id=...)` (`host/host.py`).
- [ ] T006 Surface the field from both backends: `checkpoint/file.py` and
  `checkpoint/sqlite.py` `list_sessions` populate `principal_id=meta.payload.principal_id`;
  extend the shared checkpoint contract suite (`tests/contract/test_checkpoint_sqlite.py`)
  with a `principal_id` round-trip over both backends.

**Checkpoint**: `Principal`/verifier exist; the owner can ride durable metadata; tests in
T002 still fail only on the missing ownership enforcement.

---

## Phase 3: User Story 1 — a principal sees/drives only their own sessions (P1) 🎯 MVP

**Goal**: ownership scoping on listing and every per-session route.

**Independent Test**: two principals; each lists only its own; cross access 404s (T002).

- [ ] T007 [US1] `src/loopplane/webapi/sessions.py`: add `SessionEntry.owner`; `run_session`
  records the owner and passes `principal_id=owner` into `host.session(...)` so the live
  session's durable metadata carries it.
- [ ] T008 [US1] `src/loopplane/webapi/app.py`: inject `principal: Principal = Depends(require)`
  into every route (replacing the router-level discarded dependency); `open_session` tags
  `owner=principal.id`; `GET /sessions` returns only summaries with
  `principal_id == principal.id`; the live `_require` 404s when the entry is missing or
  `entry.owner != principal.id`; the durable routes (history/resume/artifacts) 404 when the
  listed owner is not the caller.

**Checkpoint**: T002's US1 scoping assertions pass; Alice and Bob are isolated.

---

## Phase 4: User Story 2 — ownership survives a restart (P2)

**Goal**: durable per-principal scoping via the checkpoint metadata.

**Independent Test**: A persists a session; a fresh app over the same storage → A
lists/resumes it, B cannot.

- [ ] T009 [US2] Add the restart case to `test_webapi_principal_scoping.py`: Alice runs a
  session against `StorageConfig(root=tmp)`; build a fresh `create_app` over the same
  storage; assert Alice's listing includes it and resume succeeds, and Bob's listing
  excludes it and resume returns `404`. (Exercises the T005/T006 durable owner.)

---

## Phase 5: User Story 3 — default-deny + public-safety hold (P3)

**Goal**: the boundary's safety posture is preserved while it gains identity.

**Independent Test**: no authenticator → all `401`; raising verifier → `401`; no leak.

- [ ] T010 [US3] Confirm T002's default-deny / raising-verifier / no-credential-leak
  assertions pass against the implemented boundary; add a public-safety assertion that a
  `401` and a cross-owner `404` body carry only the fixed envelope (no credential, no
  principal, no session existence signal).

---

## Phase 6: Polish — drift, changelog, board, gates

- [ ] T011 [P] `docs/api-reference.md`: add `Principal` and `token_authenticator` to the
  `loopplane.webapi` section (api-reference `__all__` drift contract).
- [ ] T012 [P] `CHANGELOG.md`: add a `022` entry under Added; **note the `Authenticator`
  return-type breaking change** (allow/deny → principal) to the 011 web/API surface.
- [ ] T013 [P] `docs/loopplane-agent-board.md`: add the **022** roadmap row + a status
  evidence note; refresh §4 "Active Feature" to reflect 022 (Phase C backend) shipped and
  unit 023 (login UI) next.
- [ ] T014 Run the gates: `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy`, `uv run pytest` — all green; `uv build` succeeds; the packaging extras
  test is unchanged and the public-safety scan is clean.
- [ ] T015 Final review: confirm the runtime loop/gateway/event-bus are unchanged,
  `principal_id` is byte-identical when unset, and concurrency/login UI are deferred;
  record unit 022 on the board; commit (`022 implement`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T006)** precede the stories. T002 (tests) is
  written first and FAILS until enforcement exists. The additive plumbing (T005/T006) is a
  prerequisite for US1's list-filter + durable owner.
- **US1 (T007–T008)** depends on T003 (Principal/dependency) and T005/T006 (host.session
  principal_id + `SessionSummary.principal_id`).
- **US2 (T009)** depends on T005/T006 (durable owner) and US1's enforcement.
- **US3 (T010)** depends on T003/T008 (the boundary + enforcement).
- **Polish (T011–T015)** depends on the public surface (T003/T004) and the implemented
  enforcement.

### Parallel opportunities

- T001 is independent `[P]`.
- T011/T012/T013 (api-reference / changelog / board) are independent `[P]` files.

## Notes

- **404, not 403**, for non-owners — never leak another principal's session existence.
- The `principal_id` plumbing is **optional, default `None`** — with it unset the runtime
  paths, serialized records, and listings are byte-identical (existing tests unaffected).
- `controller.resume` is **not** changed; the web/API gates resume by the listed owner.
- The host stays **single + sequential**; this unit adds ownership scoping, not concurrent
  execution. Ownerless legacy durable sessions are listed to no one.
- Rollback = revert the boundary to `→ bool`, drop `SessionEntry.owner` + the ownership
  checks, and remove the optional `principal_id` field.
