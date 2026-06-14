---
description: "Task list for Web / API Host (011)"
---

# Tasks: Web / API Host

**Input**: Design documents from `/specs/011-loopplane-web-api-host/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL before
implementation), then implements until green. All tests run **in-process** via Starlette's `TestClient` —
no real socket, no external network (NFR-006/NFR-007).

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases IA–IF map below; the app factory,
response models, and the auth boundary wiring are Foundational (every route needs them). US1 (start a run) is
the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/webapi/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Host Application Interface (`loopplane.host`: `LoopPlaneHost`,
`build_host`, `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`, `ToolSpec`) and the public
Phase-1 event serialization (`loopplane.events`: `EventSink`, `RuntimeEvent`, `serialize_event`), plus the
`fastapi` / `starlette` transport and stdlib. It MUST NOT import a runtime internal
(`loopplane.controller`, `loopplane.gateway`, `loopplane.dispatcher`, `loopplane.loop`) or a sibling layer,
MUST **execute no tool** (Constitution V) and **re-emit no live bus** (Constitution VI; it consumes
`on_event` and forwards `serialize_event`), and MUST keep **response bodies metadata-only** — history is
projected to `{role, block_count}`, never raw `ContentBlock` text (FR-016, NFR-006). See
[contracts/web-boundary.md](./contracts/web-boundary.md). No Phase-1/2/10 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.webapi` package skeleton: `src/loopplane/webapi/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 Add the transport dependency in `pyproject.toml`: a new `[project.optional-dependencies] web = ["fastapi>=0.111"]` extra, and add `fastapi>=0.111` + `httpx>=0.27` to `[dependency-groups] dev` (mirroring the `mcp` / `otel` pattern). Note: `fastapi` 0.111 + `httpx` 0.28 are already present in the environment, so the floor matches what is installed (no feature beyond 0.111 is used).
- [X] T003 [P] Add webapi test helpers in `tests/webapi_helpers.py`: a public-safe deterministic fake model (reusing the host suite's `ScriptedModel` pattern), a `build_test_host(working_scope, *, model=None, tools=(ECHO_TOOL,), approval=None)` returning a `LoopPlaneHost`, `allow_all` / `deny_all` / `accept_valid` / `raising` authenticators, and a `make_client(app)` building a Starlette `TestClient`; guard the module with `pytest.importorskip("fastapi")`.

---

## Phase 2: Foundational (Blocking Prerequisites — app factory, models, auth boundary)

**Purpose**: The app factory, the metadata-only response models, and the fail-safe auth boundary every route
composes. **⚠️ Blocks US1–US5.**

- [X] T004 [P] Write unit tests in `tests/unit/test_webapi_core.py` (`pytest.importorskip("fastapi")`): `HistoryEntryView` is `{role, block_count}` only; `RunResult.from_outcome` projects a `RunOutcome` and the block text never appears in the serialized response (FR-016); `ErrorResponse` is `{detail}` only; the auth dependency over a tiny guarded app admits `allow_all`, denies `DENY_ALL`/missing/wrong/raising → `401`, admits a valid credential, and never echoes the credential (FR-013–FR-015); `create_app` smoke. (create_app's default-deny on a real route is exercised by US1/US5 once routes exist.)
- [X] T005 [P] Implement `src/loopplane/webapi/models.py`: the pydantic `RunRequest`, `HistoryEntryView`, `RunResult`, `SessionSummaryView`, `OpenedSession`, `Resolved`, `ArtifactContent`, `SessionAnswer`, `QuestionAnswer`, and `ErrorResponse` models, plus the `RunOutcome` → `RunResult` and `SessionSummary` → view projections (metadata-only). `SessionSummary` is read via a structural `_SummaryLike` Protocol (it is not a public host export), keeping the import boundary clean (FR-016, NFR-006; [data-model.md](./data-model.md)).
- [X] T006 [P] Implement `src/loopplane/webapi/auth.py`: the `Authenticator` type, the `DENY_ALL` default, and `make_auth_dependency` — the FastAPI dependency that reads the `Authorization` header, calls the authenticator, and denies on missing / falsy / **raising** → `401` `{"detail": "unauthorized"}` (never echoing the credential) (FR-013–FR-015, NFR-005).
- [X] T007 Implement `src/loopplane/webapi/app.py`: `create_app(host, *, authenticator=None, api_prefix="/v1") -> FastAPI` building an auth-guarded `APIRouter` and a `RequestValidationError` handler → `422` `ErrorResponse(detail="invalid request")`; finalize `__init__.py` exports (`create_app`, `Authenticator`, the public models). (The sequential-run `409` mapping lands with `POST /runs` in US1; the session-registry lifespan lands with US3, where the registry lives.)
- [X] T008 Run `pytest tests/unit/test_webapi_core.py --basetemp=".pytmp"` → green (gate for Foundational).

**Checkpoint**: The app factory, metadata-only models, and default-deny auth boundary are ready.

---

## Phase 3: User Story 1 - Start and observe a run over the API (Priority: P1) 🎯 MVP

**Goal**: `POST /runs` starts one run through the embedded host and returns its public-safe `RunResult`.

**Independent Test**: POST a prompt with a valid credential → a `RunResult` (metadata-only); a concurrent
run → `409`; a malformed body → a public-safe `4xx`.

- [X] T009 [P] [US1] Write integration tests in `tests/integration/test_webapi_us1.py`: with an `allow_all` authenticator, `POST /v1/runs {prompt}` returns `200` with a `RunResult` (session_id, `termination_reason`, integer `turns_taken`, metadata `history` of `{role, block_count}` with **no** block text — asserts the run's own content does not leak); a malformed/empty body → `422` `{"detail": "invalid request"}`; no credential → `401`; a sequential-run conflict (stub host raising `RuntimeError`) → `409` (US1 scenarios 1–3; SC-001, FR-001–FR-003, FR-016).
- [X] T010 [US1] Implement the `POST /runs` route in `src/loopplane/webapi/app.py`: drive `host.run(prompt, on_event=_discard)`, project `RunOutcome` → `RunResult`, map a sequential-run `RuntimeError` → `409` (FR-001–FR-003).
- [X] T011 [US1] Run `pytest tests/integration/test_webapi_us1.py --basetemp=".pytmp"` → green (4 passed; full suite 510).

**Checkpoint**: MVP — a client drives a run over the API and gets a metadata-only outcome.

---

## Phase 4: User Story 2 - Stream run events to a connected client (Priority: P2)

**Goal**: `POST /runs/events` streams the run's normalized events (SSE) in recorded order, then a terminal
outcome frame.

**Independent Test**: Read the SSE stream while a run executes; assert each frame equals
`serialize_event(event)` in recorded order; a mid-stream disconnect never crashes/hangs the run.

- [X] T012 [P] [US2] Write integration tests in `tests/integration/test_webapi_us2.py`: `POST /v1/runs/events {prompt}` streams `text/event-stream`; each `data:` frame is a `serialize_event` document (carries `type`/`sequence`) in **recorded order** (sequences ascending; first `user-input`, last `run-terminated`), followed by an `event: outcome` frame (the metadata-only `RunResult`); the type order is identical on repeat (determinism); disconnecting mid-stream never hangs/crashes — a fresh run still succeeds (US2 scenarios 1–3; SC-002/005, FR-004–FR-006, NFR-004).
- [X] T013 [US2] Implement `src/loopplane/webapi/streaming.py` (`run_event_stream`: drives `host.run` on an **unbounded** `anyio` memory stream so a sink send never blocks the run, frames each event via `serialize_event`, suppresses broken/closed-channel errors so a gone client never crashes/hangs the run, then a final `outcome`/`error` frame) and the `POST /runs/events` route in `app.py` (a `StreamingResponse` draining the channel in a task group) (FR-004–FR-006).
- [X] T014 [US2] Run `pytest tests/integration/test_webapi_us2.py --basetemp=".pytmp"` → green (3 passed; full suite 513).

**Checkpoint**: US1 + US2 — run and a deterministic, fail-safe event stream.

---

## Phase 5: User Story 3 - Conduct an interactive session over the API (Priority: P3)

**Goal**: open a session, submit input, answer a pending approval/question out-of-band, and cancel — over
the embedded `Session`.

**Independent Test**: open → submit (triggers an approval surfaced on the session stream) → answer the
approval by id → the run proceeds; cancel never hangs; an unknown id → an explicit negative result.

- [X] T015 [P] [US3] Write integration tests in `tests/integration/test_webapi_us3.py`: `POST /v1/sessions` → `OpenedSession` + `cancel`; an unknown session → `404` (submit/cancel/events); `submit` to a session → `200` outcome; an unknown `request_id` → `Resolved{resolved:false}` (approval + question). **Coverage note**: the session's *live* events stream is an infinite SSE response the buffering in-process `TestClient` cannot read incrementally, so the mid-stream out-of-band approval round-trip is not exercised at the HTTP level — the SSE framing is proven by the US2 finite-stream tests and the Session-level approval/cancel round-trip by the Phase-2 host suite (FR-007–FR-010).
- [X] T016 [US3] Implement `src/loopplane/webapi/sessions.py` (`SessionEntry` + `run_session`: a lifespan-task-group-held `async with host.session(sink)` keyed by the public `session_id`, an unbounded SSE channel, a `close` event, conflict signalled via `box['error']`) and the session routes in `app.py` (open / events / submit / approvals / questions / cancel) over a lifespan-scoped task group. `submit` drives the live `Session` to its outcome (FR-007–FR-010).
- [X] T017 [US3] Run `pytest tests/integration/test_webapi_us3.py --basetemp=".pytmp"` → green (4 passed).

**Checkpoint**: US1–US3 — run, stream, and an interactive session.

---

## Phase 6: User Story 4 - Inspect sessions, history, and artifacts over the API (Priority: P4)

**Goal**: read-only `GET /sessions`, `GET /sessions/{id}/history`, `POST /sessions/{id}/resume`, and
`GET /sessions/{id}/artifacts/{ref}` — metadata-only.

**Independent Test**: after a run, list sessions, fetch a metadata-only history snapshot, resume, and
retrieve an artifact; unknown ids/references → an explicit not-found.

- [X] T018 [P] [US4] Write integration tests in `tests/integration/test_webapi_us4.py`: after a run on a storage-backed host, `GET /v1/sessions` → `SessionSummaryView`s (`{session_id, label}`); `GET /v1/sessions/{id}/history` → `HistoryEntryView`s with **no** block text (asserts no content leak); `POST /v1/sessions/{id}/resume` → `200` and an unknown session → `404`; `GET /v1/sessions/{id}/artifacts/{ref}` → `404` `not found` for an unknown reference; an unknown session history → `404` (US4 scenarios 1–3; SC-003, FR-011/FR-012, FR-016).
- [X] T019 [US4] Implement the inspection routes in `src/loopplane/webapi/app.py`: delegate to `host.list_sessions` / `host.history_snapshot` / `host.resume` / `host.retrieve_artifact`, projecting to metadata-only views and mapping `KeyError`/`RuntimeError`/`None` → `404` (FR-011, FR-012).
- [X] T020 [US4] Run `pytest tests/integration/test_webapi_us4.py --basetemp=".pytmp"` → green (4 passed; full suite 521).

**Checkpoint**: US1–US4 — run, stream, session, and inspection.

---

## Phase 7: User Story 5 - Guard every request behind an authentication boundary (Priority: P5)

**Goal**: prove and harden the auth boundary (built in Foundational) on every route — default-deny,
fail-safe, no credential echo.

**Independent Test**: a missing / rejected / **raising**-verifier credential → `401`; a valid credential →
admitted; a no-authenticator app denies all; no response echoes the credential.

- [X] T021 [P] [US5] Write integration tests in `tests/integration/test_webapi_us5.py`: with **no** authenticator every route group (run / session / inspection) → `401`; with a verifier, a missing or wrong credential → `401`, a raising verifier → `401` (not `500`), a valid credential → admitted; the `401` body is `{"detail": "unauthorized"}` and never echoes the credential (US5 scenarios 1–3; SC-004, FR-013–FR-015, NFR-005).
- [X] T022 [US5] Every route is guarded by the single router-level auth dependency (`APIRouter(dependencies=[Depends(make_auth_dependency(auth))])`); the US5 tests confirm run/session/inspection routes all enforce it with a uniform `401` envelope and deny-on-raise — no per-route change needed (FR-013–FR-015).
- [X] T023 [US5] Run `pytest tests/integration/test_webapi_us5.py --basetemp=".pytmp"` → green (4 passed; full suite 525).

**Checkpoint**: All user stories are independently functional behind a fail-safe auth boundary.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T024 [P] Write contract tests in `tests/contract/test_webapi_boundary.py` (`pytest.importorskip("fastapi")`): an import-boundary audit (every `src/loopplane/webapi/*.py` imports only `loopplane.host` / `loopplane.events` + `fastapi` / `starlette` + stdlib, and references no `loopplane.controller` / `loopplane.gateway` / `loopplane.dispatcher` / `loopplane.loop` / sibling-layer token); a **no-tool-exec / no-reemit** audit (the only event path is `on_event` → `serialize_event`); a **metadata-only** response assertion (a `RunResult` / history view carries no block text); a **default-deny** assertion (no-authenticator app denies); SSE-order **determinism** (NFR-001/002/003/004, SC-002/003/006).
- [X] T025 [P] Extend `tests/contract/test_public_safety.py` with `PHASE11_TARGETS` (`src/loopplane/webapi`, `examples/webapi_quickstart.py`, `docs/web-api-host.md`, `specs/011-loopplane-web-api-host`) and a `test_phase11_webapi_files_are_public_safe` scan.
- [X] T026 [P] Create `examples/webapi_quickstart.py`: a public-safe, credential-free runnable that builds a host with the fake model, calls `create_app`, and drives a run + an SSE stream + an auth check through the in-process `TestClient`, printing only public-safe outcomes (per [quickstart.md](./quickstart.md)).
- [X] T027 [P] Create `docs/web-api-host.md`: a public-safe guide — endpoints, the SSE event stream (Constitution VI: forward `serialize_event`, never re-emit), the default-deny auth boundary, embedding via `create_app`, and the reserved extension points.
- [X] T028 Finalize `src/loopplane/webapi/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [X] T029 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/webapi_quickstart.py`; confirm the public-safety scan is green (SC-003/006); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (app factory, models, auth boundary).
- **US1 (Phase 3)**: depends on Foundational. MVP (start a run).
- **US2 (Phase 4)**: depends on Foundational + US1's `POST /runs` (adds the streaming variant + `streaming.py`).
- **US3 (Phase 5)**: depends on Foundational; adds `sessions.py` + session routes.
- **US4 (Phase 6)**: depends on Foundational; read-only inspection routes (best after US3 so sessions exist).
- **US5 (Phase 7)**: depends on Foundational (the auth boundary already exists there); proves/hardens it.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- The models/auth/app factory before the routes; each phase ends on its pytest gate; commit per stable phase.

## Parallel Opportunities

- T003 (helpers) runs alongside the Phase-2 test authoring.
- Foundational: `models.py` (T005), `auth.py` (T006) are independent files (`[P]`); `app.py` (T007) composes them.
- Across stories: `streaming.py` (US2) and `sessions.py` (US3) are independent files — their `[P]` test
  authoring can proceed in parallel once Foundational is green; the `app.py` route additions serialize on that file.
- Polish: T024–T027 are independent files (`[P]`); T028/T029 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (app factory + models + auth boundary) → Phase 3 US1 (`POST /runs`).
2. **STOP and VALIDATE**: a client drives a run over the API behind the auth boundary and gets a
   deterministic, metadata-only outcome — in-process, offline.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (event stream) → US3 (interactive session) → US4 (inspection) → US5 (auth
hardening) → Polish. Each phase is an independently testable, revertible increment; no Phase-1/2/10 source is
modified; the `web` extra is optional.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every response body is metadata-only (no raw history blocks / tool I/O); the SSE stream forwards
  `serialize_event` verbatim (Constitution VI) to an authenticated client; the auth boundary defaults to deny.
- All tests run in-process via `TestClient` — no real socket, no external egress (FR-017, NFR-006/NFR-007).
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing a runtime internal / sibling layer; executing a tool or re-emitting the live bus; leaking
  a content block, stack trace, internal type, path, or the credential in any response.
