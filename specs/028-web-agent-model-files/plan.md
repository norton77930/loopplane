# Implementation Plan: Web Agent Model Selection & File Attachments

**Branch**: `028-web-agent-model-files` (main-only) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-web-agent-model-files/spec.md`

## Summary

Two additive web-layer capabilities, **no constitution ADR** (a reference review + the runtime's
own seams confirm neither blurs a boundary — like unit 027):

1. **Per-session model selection** — resolved **entirely in the web/API layer**. `create_app`
   gains an optional **model catalog** (`models: Mapping[str, ModelHost]`, each entry = a label +
   a pre-configured single-model `LoopPlaneHost`, all sharing the **same checkpoint root** — unit
   021). `GET /v1/models` lists the catalog (metadata-only). A run carries an optional `model`
   id; the web/API layer **routes** that run to the chosen model's host, which resumes the session
   from the **shared checkpoint store** so history is preserved. The **runtime core is untouched**
   — each host has exactly **one model**, so every run receives one model (FR-004). The default
   `host` remains the fallback (backward compatible).
2. **File attachments** — an additive **`UploadStore`** (a per-reference blob store; the owning
   principal is recorded) + a `POST /v1/uploads` endpoint (auth-gated, per-principal, size-limited)
   that returns an **unguessable reference**. The message carries the reference; the agent reads
   the file **on demand** via a **`read_upload` tool registered inside the Tool Gateway**
   (Constitution V — new tools belong in the gateway) that reads the blob by reference. Files are
   **transient input by id** — **not** embedded into the content model, **not** artifacts, **not**
   memory (so the content contract is unchanged). Per-principal scoping is a **capability** model:
   `RunContext` carries no `principal_id`, so the reference is an unguessable token returned only
   to its owner; the upload endpoint records the owner and scopes the store.

Additive throughout: the runtime core, the one-model-per-run contract, the content model, the Tool
Gateway (V) and Event Bus (VI) contracts, and existing endpoints are preserved; the Python suite +
the `apps/web` gate stay green. Multimodal/embedded content (a Principle IV change) is **out of
scope**.

## Technical Context

**Language/Version**: Python 3.12 (host/webapi) + TypeScript 5.6 / React 18 (`apps/web`).

**Primary Dependencies**: backend — none new (reuses `loopplane.adapters.{anthropic,openai}` for
real model hosts when configured; `ScriptedModel` for tests; FastAPI multipart for the upload).
Frontend — none new (reuses the 025–027 toolchain).

**Storage**: a new **`UploadStore`** (file-backed blob store, keyed by an unguessable reference; the
owner principal recorded) under an operator-provided root. The shared **checkpoint store** (unit
021) is reused across the model hosts.

**Testing**: pytest — `UploadStore` unit (save/read/owner/limit); the `read_upload` tool unit (reads
by reference; missing → clear result); webapi integration (catalog endpoint lists models; a run
routed to the chosen model's host; upload stores per-principal + returns a reference; auth-gating;
size-limit error). Vitest + jsdom — the composer model selector + file-attach (progress/error) over
a stubbed client. Real adapters are exercised only behind their opt-in (unit 020); tests use
`ScriptedModel` hosts.

**Target Platform**: the web/API host (unit 011) + the browser SPA (unit 025).

**Project Type**: full-stack but **additive** — a model catalog + run routing + an upload endpoint +
a gateway tool + composer UI; the runtime core and existing endpoints are untouched.

**Performance Goals**: model routing is an O(1) host lookup; uploads stream to disk with a size cap.
No hard numeric target.

**Constraints**: **one model per run** (each host is single-model; selection is web/API routing —
the runtime never switches models internally, FR-004); files are **tool-read transient input**, not
embedded/artifact/memory (content model unchanged, FR-007); **auth-gated + per-principal** (FR-008);
configurable **limits** with clear errors (FR-009); additive (runtime/gateway/bus/existing endpoints
preserved); no secret or legacy UI committed (FR-010 / VII); no SDK replacement (VIII); both gates
green.

**Scale/Scope**: a model catalog + routing in `create_app`/run endpoints; a new `UploadStore` +
`read_upload` tool + upload endpoint; frontend model selector + file-attach in the composer; tests +
docs/board. Two user stories P1–P2.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS** (no ADR).*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–010; SC-001–006), grounded in a backend audit. | PASS |
| II — Greenfield | New web/host/UI code written fresh; no legacy UI copied (VII). | PASS |
| III — Harness before automation | No loop automation; model selection is host routing, not runtime change. | PASS |
| IV — Boundary Clarity | The **content model is unchanged** — files are tool-read transient input (not embedded); model selection is web-layer routing over the existing host seam. The one Principle-IV change (embedded content) is **out of scope**. | PASS |
| V — Tool Gateway Ownership | The `read_upload` tool is registered **inside** the gateway via `config.tools` (V explicitly permits new tools in the gateway); no bypass path. | PASS |
| VI — Event Bus Ownership | No event schema change; runs still emit the normalized stream. | PASS |
| VII — Public-Safe | The upload reference is an unguessable token; no secret/path/internal name committed; the catalog is metadata-only (ids/labels, never api keys). | PASS |
| VIII — No SDK Replacement | Reuses the unit-020 adapters behind the existing model boundary; no framework swap. | PASS |
| IX — Reference, not clone | A conventional model selector + attachment flow, derived for this app (and it exceeds the reference — the agent can read the file). | PASS |
| X — Testable Evolution | Store + tool + webapi + UI tests; **rollback** = drop the catalog/routing + the upload endpoint/store/tool + the composer UI → the prior single-model, text-only app returns. | PASS |

No violations — Complexity Tracking is intentionally empty. **No ADR**: the runtime keeps one model
per run (selection is web-layer routing) and files are tool-read transient input (content model
unchanged); only embedded multimodal content would need a Principle IV ADR, and it is out of scope.

## Project Structure

### Documentation (this feature)

```text
specs/028-web-agent-model-files/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── model-and-uploads.md   # catalog + run routing + upload endpoint + read_upload tool contracts
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/loopplane/webapi/
├── uploads.py         # NEW — UploadStore (per-reference blob store; owner recorded; size limit) + read_upload ToolSpec factory
├── models.py          # EDIT — ModelInfo/ModelCatalogView; RunRequest.model; UploadResult view
└── app.py             # EDIT — models catalog param + GET /v1/models; route runs to the chosen host; POST /v1/uploads (multipart, auth-gated)

tests/
├── unit/test_uploads.py                 # NEW — UploadStore + read_upload tool (save/read/owner/limit/missing)
└── integration/test_webapi_model_files.py # NEW — catalog lists models; run routed to chosen host; upload per-principal + reference; auth; size-limit

apps/web/src/
├── api/
│   ├── types.ts       # EDIT — ModelInfo, UploadResult
│   └── client.ts      # EDIT — listModels(); uploadFile(file) (progress); model param on run/open
├── components/
│   ├── ModelSelector.tsx   # NEW — pick the session's model (composer)
│   ├── Attachments.tsx     # NEW — attach files (picker/drop) + per-file progress/error
│   └── Composer.tsx        # EDIT — embed the model selector + attachments; carry the model + references on send
└── App.tsx            # EDIT — hold the selected model + attachments; pass the model to runs; include references on the prompt
```

Edited (docs / drift): `docs/web-api-host.md` (+ model catalog / uploads), `docs/web-frontend.md`
(+ model selector / attachments), `CHANGELOG.md` (028 entry), `docs/loopplane-agent-board.md`
(028 → Verified; advance §4 to 029), `CLAUDE.md` (marker → 028 plan).

**Structure Decision**: Both capabilities are **web/API-layer additions over existing seams**.
Model selection is a **catalog of pre-built single-model hosts** (reusing unit-020 adapters; tests
use `ScriptedModel`) all sharing the **unit-021 checkpoint root**, with the run **routed** to the
chosen host — the runtime keeps one model per run (Principle IV/VIII untouched). File attachments
are an `UploadStore` + a `POST /v1/uploads` endpoint + a `read_upload` **gateway tool** (Principle V)
— files are read on demand by reference, never embedded (content model unchanged). Because
`RunContext` carries no `principal_id`, per-principal scoping is a **capability**: the upload records
the owner and returns an unguessable reference only to that owner; the tool reads by reference.

## Phases

- **Phase 0 — Research** (`research.md`): the audited model boundary + adapters + `ScriptedModel`;
  the catalog-of-hosts + shared-checkpoint routing decision (and why it keeps one-model-per-run);
  the capability-scoping decision for uploads (RunContext lacks `principal_id`); the `read_upload`
  gateway-tool design; the limits/error model; and the deferral of embedded multimodal content.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the catalog + selection
  types; the `UploadStore` + reference model; the `read_upload` tool I/O; the endpoint contract; and
  a quickstart.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD, P1 → P2 — the catalog + run routing + endpoint + tests
  (P1); the UploadStore + read_upload tool + upload endpoint + tests (P2); the frontend selector +
  attachments + composer wiring + tests; docs/board; both gates.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
