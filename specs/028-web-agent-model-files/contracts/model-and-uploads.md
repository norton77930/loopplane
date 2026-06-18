# Contract: Model Selection & File Uploads (additive, web/API layer)

Additive endpoints + a gateway tool over existing seams. The runtime core, the one-model-per-run
contract, the content model, the Tool Gateway (V), the Event Bus (VI), and existing endpoints are
**preserved**.

## Model catalog + routing

| Method + path | Returns / effect |
|---|---|
| `GET /v1/models` | `list[ModelInfo { id, label }]` — the operator-configured catalog, metadata-only (FR-001) |
| `POST /v1/runs` / `POST /v1/runs/events` (+ session submit) | accept optional `model` id; route the run to `models[model].host` (else the default `host`); unknown id → `400` (FR-002/003) |

### Guarantees

1. **One model per run.** Each catalog entry is a single-model host; routing selects which host runs
   — the runtime is **never** made to switch models internally (FR-004). Selection is resolved
   **entirely in the web/API layer**.
2. **Shared history.** All catalog hosts share the **same checkpoint root** (021), so a later turn
   routed to a different model's host resumes the session and history is intact (edge case).
3. **Metadata-only catalog.** `ModelInfo` is `{ id, label }` — never an api key or provider secret
   (VII).
4. **Auth-gated.** The catalog + routed runs honor the existing boundary (`Depends(require)`,
   FR-008).

## Upload endpoint + read_upload tool

| Method + path | Returns / effect |
|---|---|
| `POST /v1/uploads` (multipart, auth-gated) | store the file under the caller's principal; return `UploadResult { reference, name }`; over-limit/invalid → clear `4xx` error (FR-005/006/009) |
| `read_upload` (Tool Gateway tool) | `read_upload({ reference })` → the file's text as an `OutputBlock` (bounded); missing/oversized → a public-safe "not found"/"too large" block (FR-007) |

### Guarantees

1. **Transient input by id.** An attachment is a per-reference blob read **on demand** via the
   gateway tool — **not** embedded into the prompt/content model, **not** an artifact, **not** memory
   (FR-007). The content contract is unchanged (Principle IV untouched).
2. **Gateway-owned tool.** `read_upload` is registered **inside** the Tool Gateway via `config.tools`
   (Constitution V); it **reads only** (no write/execute/mutation beyond reading the blob); no bypass
   path is added.
3. **Capability scoping.** `RunContext` carries no `principal_id`; the **unguessable reference** is
   the capability — the upload records the owner and returns the reference only to that caller, and
   the store is never listed, so a principal can only reference its own uploads (FR-008).
4. **Limits + errors.** A configurable max size (and optional type allowlist) is enforced with a
   clear error; the message is not sent with a missing attachment (FR-005/009).

## Frontend

A `ModelSelector` (lists `GET /v1/models`, shows the current choice) and an `Attachments` control
(picker/drag-drop, per-file progress + error) in the composer. The selected `model` id rides the
run; uploaded references are appended to the prompt so the agent can `read_upload` them. The send is
blocked while any attachment is uploading or errored.

## Verification

- `tests/unit/test_uploads.py`: `UploadStore` save/read/info, owner recorded, over-limit raises,
  missing reference → None; the `read_upload` tool returns the text and a public-safe block on
  missing.
- `tests/integration/test_webapi_model_files.py`: `GET /v1/models` lists the catalog; a run with
  `model=X` is served by host X (a distinguishable `ScriptedModel`); an unknown id → 400; the upload
  stores per-principal and returns a reference; uploads/catalog are auth-gated; over-limit → a clear
  error.
- `apps/web` Vitest: the `ModelSelector` lists + selects; `Attachments` uploads with progress and
  surfaces an error; the composer carries the model + references on send.
