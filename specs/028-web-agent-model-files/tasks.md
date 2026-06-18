---
description: "Task list for unit 028 — Web Agent Model Selection & File Attachments (additive, no ADR)"
---

# Tasks: Web Agent Model Selection & File Attachments

**Input**: Design documents from `specs/028-web-agent-model-files/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/model-and-uploads.md

**Tests**: REQUIRED (Constitution X). pytest (UploadStore + read_upload tool unit; webapi
integration) + Vitest/jsdom (selector + attachments). Write tests FIRST and confirm they FAIL.

**Scope guard**: **additive, no ADR**. Model selection is **web/API-layer routing** to a catalog of
pre-built single-model hosts sharing the unit-021 checkpoint root (runtime keeps **one model per
run**). Files are an upload endpoint + a `read_upload` **gateway tool** (Constitution V) reading
**transient input by id** — **not** embedded into the content model, artifacts, or memory.
**No** runtime/content/Tool-Gateway/Event-Bus/existing-endpoint change. The upload endpoint uses a
**raw octet-stream body + `?name=`** (no `python-multipart` dependency). Both gates green at the
implement commit.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency** — backend reuses the `web` extra (raw-body upload, no
  `python-multipart`) and the unit-020 adapters (only when configured; tests use `ScriptedModel`);
  `apps/web` toolchain unchanged.

---

## Phase 2: User Story 1 - Choose the model a session uses (Priority: P1) 🎯 MVP

**Goal**: a model catalog + per-run model selection routed in the web/API layer; one model per run.

**Independent Test**: `GET /v1/models` lists the catalog; a run with `model=X` is served by host X;
an unknown id → 400; the catalog/runs are auth-gated.

- [ ] T002 [P] [US1] Write `tests/integration/test_webapi_model_files.py` FIRST (FAIL) for the model
  path: `GET /v1/models` lists `{id,label}` for a two-model catalog (distinguishable `ScriptedModel`
  hosts sharing one checkpoint root); `POST /v1/runs` (and `/runs/events`) with `model=X` is served
  by host X's model (assert the distinguishable output); an unknown `model` → 400; both auth-gated.
- [ ] T003 [US1] Backend: `src/loopplane/webapi/models.py` — add `ModelInfo { id, label }` and
  `RunRequest.model: str | None = None`. `src/loopplane/webapi/app.py` — `create_app(host, *,
  models: Mapping[str, ModelHost] | None = None, …)`; add `GET /v1/models`; a `_select_host(model)`
  helper routes `POST /runs` + `POST /runs/events` (and the session submit) to `models[model].host`
  (else the default `host`; unknown id → `HTTPException(400)`). Make the model cases of T002 pass.
- [ ] T004 [P] [US1] Frontend: `apps/web/src/api/types.ts` (`ModelInfo`) + `apps/web/src/api/client.ts`
  (`listModels()`; pass `model` on the run); `apps/web/src/components/ModelSelector.tsx` (lists models,
  indicates the current choice); wire it into `Composer.tsx`; `App.tsx` holds `selectedModel` and
  passes it to runs. Add `apps/web/src/__tests__/ModelSelector.test.tsx`.

**Checkpoint**: a user sees + selects a model; the run is routed to it; one model per run.

---

## Phase 3: User Story 2 - Attach a file to a message (Priority: P2)

**Goal**: an upload endpoint + a `read_upload` gateway tool; the agent reads attachments on demand.

**Independent Test**: a file uploads (per-principal) and returns a reference; the agent reads it via
`read_upload`; over-limit/failed uploads error clearly.

- [ ] T005 [P] [US2] Write `tests/unit/test_uploads.py` FIRST (FAIL): `UploadStore.save/read/info`
  (owner recorded; unguessable reference; over-limit raises; missing reference → None); the
  `read_upload` tool returns the file text as an `OutputBlock` and a public-safe "not found" block
  for a missing reference (never raises).
- [ ] T006 [US2] Backend: `src/loopplane/webapi/uploads.py` — `UploadStore(root, *, max_bytes)`
  (`save(owner, name, data) -> StoredUpload`, `read(reference) -> bytes | None`, `info(...)`) +
  `make_read_upload_tool(store) -> ToolSpec` (descriptor `read_upload`, read-only; handler reads by
  reference, bounded text, public-safe on missing/oversized). Make T005 pass.
- [ ] T007 [US2] Backend: `models.py` add `UploadResult { reference, name }`; `app.py` —
  `create_app(..., uploads: UploadStore | None = None)`; `POST /v1/uploads` (auth-gated; raw
  octet-stream body + `?name=`; size-limited; stores under the caller's principal; returns
  `UploadResult`; over-limit/invalid → clear `4xx`). Add the upload integration cases to T002's file
  (per-principal store + reference; auth-gated; size-limit error). The operator wires
  `make_read_upload_tool(store)` into each host's `config.tools`.
- [ ] T008 [P] [US2] Frontend: `apps/web/src/api/types.ts` (`UploadResult`) + `client.ts`
  (`uploadFile(file)` with progress); `apps/web/src/components/Attachments.tsx` (picker/drag-drop,
  per-file progress + error); wire into `Composer.tsx` (append done references to the prompt; block
  send while uploading/errored); `App.tsx` holds attachments. Add
  `apps/web/src/__tests__/Attachments.test.tsx`.

**Checkpoint**: a user attaches files (progress/error) the agent can read via `read_upload`.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T009 [P] Docs: `docs/web-api-host.md` (+ model catalog / uploads) and `docs/web-frontend.md`
  (+ model selector / attachments).
- [ ] T010 [P] `CHANGELOG.md`: add a `028` entry under Added.
- [ ] T011 [P] `docs/loopplane-agent-board.md`: set **028 → Verified** with a status-evidence note;
  advance §3/§4 to make **029** the active unit.
- [ ] T012 Run the gates: **`pytest`** (full suite green — additive, SC-004) incl. the new unit +
  integration tests; `apps/web` `npm run typecheck` + `npm test` + `npm run build` green;
  public-safety scan clean (no secret/path/internal name; the model catalog carries **no api key**;
  the upload reference leaks nothing; no legacy UI copied — VII).
- [ ] T013 Final review: confirm **additive** (runtime / one-model-per-run / content model / Tool
  Gateway / Event Bus / existing endpoints unchanged), **no ADR**, auth-gated + per-principal, and
  the rollback (drop the catalog/routing + upload endpoint/store/tool + composer UI); commit
  (`feat: implement LoopPlane web-agent-model-files`).

---

## Dependencies & Execution Order

- **Setup (T001)** precedes the stories.
- **US1 (T002–T004)** is the MVP (model catalog + routing + selector).
- **US2 (T005–T008)** is independent of US1 (uploads + read tool + attachments).
- **Polish (T009–T013)** depends on both stories; both gates run green before the commit.

### Within each story / parallel opportunities

- Tests first and FAIL before implementation (T002, T005).
- T004 / T008 (frontend) are independent `[P]` of the backend once the contract is fixed; docs
  T009/T010/T011 are independent `[P]` files.

---

## Implementation Strategy

MVP = US1 (model selection — unblocks the real adapters from the UI). Then US2 (attachments) →
polish. Both are additive web-layer changes; the runtime keeps one model per run and the content
model is unchanged.

## Notes

- **Model**: a catalog of single-model hosts sharing the unit-021 checkpoint root; the web/API layer
  routes a run to the chosen host (one model per run). `ScriptedModel` hosts in tests; the unit-020
  adapters only when an operator configures them.
- **Files**: capability scoping — `RunContext` carries no `principal_id`, so the unguessable
  reference (returned only to its owner) is the capability; the `read_upload` gateway tool reads by
  reference. Files are transient input by id — **not** embedded/artifact/memory (content model
  unchanged). The upload endpoint uses a raw octet-stream body (no `python-multipart`).
- **Rollback**: drop the catalog/routing + the upload endpoint/store/tool + the composer model
  selector/attachments → the prior single-model, text-only app returns (X).
