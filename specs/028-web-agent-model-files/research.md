# Phase 0 Research: Web Agent Model Selection & File Attachments

Grounded in a read-only backend audit. No `[NEEDS CLARIFICATION]` markers; the open items were how
to deliver both capabilities **additively** (no ADR).

## R1 — The audited seams (grounded)

| Concern | API | Notes |
|---|---|---|
| Model boundary | `ModelBoundary` Protocol (`model/boundary.py`): `stream_turn(request)`, `context_capacity()` | `RuntimeConfig.model: ModelBoundary`; one model per host |
| Adapters (020) | `AnthropicModel(AnthropicConfig(model=…))`, `OpenAIModel(OpenAIConfig(model=…))` | each behind its optional extra; a host per model |
| Test model | `ScriptedModel(script, context_capacity)` (`loopplane.model`) | deterministic; used by the tests |
| Checkpoint sharing | `StorageConfig(root, checkpoint_backend)`; `host.resume(session_id)` keyed by `session_id` | two hosts on the **same root** resume each other's sessions (021); `principal_id` rides the checkpoint metadata (022) |
| Tool registration | `ToolSpec(descriptor, handler)` in `config.tools`; `handler(call_input, RunContext) -> Sequence[OutputBlock]` | additive; Constitution V permits new tools in the gateway |
| RunContext | `session_id, working_scope, cancellation, turn_budget, session_approval_memory, feature_toggles, interactions` | **no `principal_id`** — drives the capability-scoping decision (R4) |

## R2 — Model selection: a catalog of single-model hosts, routed in the web/API layer

- **Decision**: `create_app(host, *, models=None, …)` accepts an optional
  `models: Mapping[str, ModelHost]` (id → `{ label, host }`), each host pre-built with one model and
  the **same `StorageConfig.root`** as the others. `GET /v1/models` lists `{ id, label }`. A run
  carries an optional `model` id; the endpoint **routes** to `models[model].host` (or the default
  `host`), which resumes the session from the shared checkpoint. The default host stays the fallback.
- **Rationale**: the runtime keeps **one model per run** (each host is single-model) — selection is
  pure web-layer routing over the existing host seam, so Principle IV/VIII are untouched and **no
  ADR** is needed. The shared checkpoint (021) preserves history when a later turn is routed to a
  different model's host (`host.resume`).
- **Alternatives considered**: making one host switch models internally (would touch the runtime
  boundary → an ADR) — rejected; a single global model (the status quo, no selection) — insufficient.

## R3 — One model per run + change between turns

- **Decision**: the run/stream endpoints (`POST /v1/runs`, `/v1/runs/events`) and the session
  submit accept the `model` id and route accordingly; the runtime always receives exactly one model
  for that run (FR-004). "Change between turns" = a subsequent run/turn carries a different `model`
  id, routed to that host, resuming from the shared checkpoint. Mid-run switching is **disallowed**
  (one model per run — edge case).
- **Rationale**: matches the spec exactly and is structurally one-model-per-run; testable by routing
  a run to a host whose `ScriptedModel` emits a distinguishable output.

## R4 — Uploads: a capability-scoped blob store + a gateway read tool

- **Decision**: a file-backed **`UploadStore`** keyed by an **unguessable reference** token, with the
  owner principal recorded. `POST /v1/uploads` (auth-gated, multipart, size-limited) saves the blob
  under the caller's principal and returns `{ reference, name }`. A **`read_upload` ToolSpec**
  (registered in each host's `config.tools`) reads the blob by reference and returns its text as an
  `OutputBlock`. The prompt carries the reference; the agent calls `read_upload(reference)`.
- **Rationale**: `RunContext` carries **no `principal_id`**, so the tool cannot re-derive the owner
  at call time. Per-principal scoping is therefore a **capability**: the reference is an unguessable
  token the upload endpoint returns **only** to its owner (the owner is recorded; listing is never
  exposed), so a principal can only reference its own uploads. The tool is a pure read-by-reference.
  Files stay **transient input by id** — not embedded into the content model, not artifacts, not
  memory (FR-007) — so the content contract is unchanged and **no ADR** is needed (Constitution V
  permits the new gateway tool).
- **Alternatives considered**: embedding file content into the prompt (a Principle IV content-model
  change → ADR) — **deferred**; storing as artifacts/memory (changes their contract) — rejected;
  per-principal host instances (heavy) — rejected.

## R5 — Limits + errors (FR-009)

- The upload enforces a configurable **max size** (and an optional content-type allowlist); over-limit
  or failed uploads return a clear public-safe error and the message is not sent with a missing
  attachment. An unknown `model` id → a clear error (not a silent wrong-model run). A model that
  becomes unavailable → a clear error (edge case).

## R6 — Frontend

- **Decision**: a `ModelSelector` (lists `GET /v1/models`, indicates the current choice) and an
  `Attachments` control (picker/drag-drop, per-file progress + error) in the composer; the selected
  `model` id rides the run, and uploaded references are appended to the prompt (e.g.,
  `[attachment: <reference>]`) so the agent can `read_upload` them. No new dependency.

**Output**: all choices resolved against the audited APIs; no open clarifications. Embedded
multimodal content is the only ADR-requiring item and is explicitly deferred.
