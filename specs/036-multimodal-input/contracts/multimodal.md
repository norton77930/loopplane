# Contracts: Multimodal Input

This unit reuses the existing `ImageBlock` content block (no new block — ADR D1)
and adds an additive capability probe + web/API image-input wiring. The
`ModelBoundary` Protocol, the content model, the event schema, the Tool Gateway,
and the artifact store are **unchanged**.

## Model-boundary capability probe (`loopplane.model`)

### `accepts_media(model: object) -> bool`

| Aspect | Contract |
|--------|----------|
| Returns | `model.accepts_media()` when the model defines that method (duck-typed via a `runtime_checkable` `MediaCapableModel` Protocol); otherwise `False` (conservative). |
| Boundary | The `ModelBoundary` Protocol is **unchanged** (`stream_turn` + `context_capacity`); this is an additive, optional capability — a non-advertising model is treated as text-only. |
| Determinism | Pure; no I/O. |

### Adapter opt-in (additive defaults)

| Implementation | `accepts_media()` |
|----------------|-------------------|
| `AnthropicModel` | returns `AnthropicConfig.accepts_media` (default `True`) |
| `OpenAIModel` | returns `OpenAIConfig.accepts_media` (default `True`) |
| `openrouter_model(...)` | default `True` (override via the `accepts_media` param) |
| `ollama_model(...)` | default `False` (override via the `accepts_media` param) |
| `ScriptedModel`, CLI demo model | do not implement it → `accepts_media(model)` is `False` |

## Web/API image input (`loopplane.webapi`)

### `RunRequest` (additive field)

| Field | Contract |
|-------|----------|
| `prompt: str` | unchanged (min length 1) |
| `model: str \| None` | unchanged (028 routing) |
| `uploads: list[UploadRef]` | **new**, optional (default `[]`); each carries an upload `reference` (028) |

`UploadRef = { reference: str }`.

### `assemble_blocks(prompt, refs, store, owner, *, accepts_media, max_image_bytes) -> list[ContentBlock]`

| Aspect | Contract |
|--------|----------|
| Output order | each **image** upload becomes an `ImageBlock`, in `refs` order, **ahead of** the trailing `TextBlock(prompt)`. |
| Non-image upload | produces **no** block (it stays a `read_upload`-readable attachment, 028). |
| Ownership | a `reference` whose stored owner is not `owner`, or that is missing, raises `UnknownUpload` (→ HTTP 400 / not-found; no cross-principal read, no existence leak — 022/028). |
| Capability | when any upload is an image and `accepts_media` is `False`, raises `MediaNotAccepted` (→ HTTP 400) **before** building any image block — the model never receives image content. |
| Size cap | an image whose bytes exceed `max_image_bytes` raises `MediaTooLarge` (→ HTTP 413); the base64 payload entering the context/event stream is bounded. |
| Empty uploads | `refs == []` → `[TextBlock(prompt)]`, identical to the prior text-only path. |
| Purity | pure (store reads only); no event emission, no run start. |

### Catalog capability

| Field | Contract |
|-------|----------|
| `ModelHost.accepts_media: bool` | operator-declared capability of a catalog host (default `False`). |
| `ModelInfo.accepts_media: bool` | `/v1/models` advertises each entry's capability so a client can adapt the attach affordance. |
| `create_app(..., default_accepts_media=False)` | the capability of the bare default `host` (no catalog) used when a run carries no `model`. |

### Run endpoints (`/v1/runs`, `/v1/runs/events`, `/v1/sessions/{id}/submit`)

| Aspect | Contract |
|--------|----------|
| Behavior | resolve the selected host + its `accepts_media`; `assemble_blocks(...)`; drive the run with the assembled `ContentBlock`s (the existing `host.run`/`session.submit` `Sequence[ContentBlock]` path). |
| Degradation | `MediaNotAccepted` / `UnknownUpload` → HTTP 400 `ErrorResponse`; `MediaTooLarge` → HTTP 413 `ErrorResponse`; never a silent wrong-content run, never a raw provider error. |
| No uploads | byte-identical to the prior text-only path. |

## Invariants

- `loopplane.model.content`, the event envelope, `SCHEMA_VERSION`, the
  `ModelBoundary` Protocol, the runtime core/Agent Loop, the Tool Gateway
  execution path, and the artifact store are **unchanged**.
- The serde round-trip test now asserts an `ImageBlock`-bearing `UserInputEvent`
  is lossless (Constitution VI — the content-block input path is proven by test).
- New public names (`accepts_media`, `RunRequest`/`UploadRef` additions, the
  assembly helper) are documented 1:1 for the unit-014 api-reference bijection;
  no committed artifact carries a secret/key/private path (Constitution VII).
- Removing the `RunRequest.uploads` field, the assembly helper, and the
  `accepts_media` flags restores the prior text-only behavior (Constitution X).
