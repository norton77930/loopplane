# Phase 1 Data Model: Multimodal Input

**No new persisted entity and no new content block.** Per ADR D1, image input
reuses the existing `ImageBlock`; the content model and the event schema are
unchanged. This unit adds an additive capability probe at the model boundary, two
adapter capability flags, and a few additive web/API request/catalog fields.

## Reused, UNCHANGED (the headline)

- **`loopplane.model.content.ImageBlock`** — `kind="image"`, `media: str`
  (base64), `format: str` (the media type, e.g. `image/png`). Already in
  `ContentBlock` and `OutputBlock`. **Unchanged.**
- **`Message.blocks: list[ContentBlock]`**, **`RuntimeController.drive(id,
  Sequence[ContentBlock])`**, **`LoopPlaneHost.run`/`Session.submit`** over
  `Prompt = str | Sequence[ContentBlock]` — already carry an `ImageBlock`.
  **Unchanged.**
- **`UserInputEvent.payload.blocks: list[ContentBlock]`** + `SCHEMA_VERSION` —
  already round-trip an `ImageBlock` (now asserted by the extended serde test).
  **Unchanged** (no version bump).
- **`UploadStore`** (028) — per-principal blob store (`save`/`read`/`info`).
  **Unchanged.**

## New / modified surface

### `loopplane.model` (capability probe — additive, non-breaking)

| Name | Kind | Meaning |
|------|------|---------|
| `accepts_media(model)` | function → `bool` | Reads `model.accepts_media()` when the model defines it (duck-typed via a `runtime_checkable` `MediaCapableModel` Protocol); otherwise returns a conservative `False`. The `ModelBoundary` Protocol is **unchanged** (still `stream_turn` + `context_capacity`). |

- Internal: `MediaCapableModel` (a `runtime_checkable` Protocol with
  `accepts_media() -> bool`) — the structural marker the helper probes. Not
  exported (an internal detail of the helper).
- `accepts_media` is added to `loopplane.model.__all__` and documented 1:1 in
  `docs/api-reference.md` (unit-014 bijection).

### Adapter capability flags (additive defaults)

| Where | Field / method | Default |
|-------|----------------|---------|
| `AnthropicConfig` | `accepts_media: bool` | `True` (Claude flagship families are vision-capable) |
| `AnthropicModel` | `accepts_media() -> bool` | returns `config.accepts_media` |
| `OpenAIConfig` | `accepts_media: bool` | `True` (GPT-4o-class models are vision-capable) |
| `OpenAIModel` | `accepts_media() -> bool` | returns `config.accepts_media` |
| `openrouter_model(...)` | `accepts_media: bool` param | `True` (brokers vision models) |
| `ollama_model(...)` | `accepts_media: bool` param | `False` (local models are commonly text-only; operator opts in) |

The two configs are frozen dataclasses with defaults, so adding a defaulted field
is non-breaking; `ScriptedModel` and the CLI demo model do **not** implement
`accepts_media`, so `accepts_media(model)` returns `False` for them.

### `loopplane.webapi` (image input at the edge — additive)

| Name | Kind | Meaning |
|------|------|---------|
| `UploadRef` | request model | `{ reference: str }` — one upload id a turn carries |
| `RunRequest.uploads` | `list[UploadRef]` | optional (default `[]`) — uploads to assemble into the user message |
| `ModelInfo.accepts_media` | `bool` | catalog advertises per-model media capability (default `False`) |
| `ModelHost.accepts_media` | `bool` dataclass field | operator-declared capability of a catalog host (default `False`); also auto-derivable via `loopplane.model.accepts_media(host model)` where exposed |
| `assemble_blocks(prompt, refs, store, owner, *, accepts_media, max_image_bytes)` | function → `list[ContentBlock]` | the pure web helper: resolve each owned upload, embed image uploads as leading `ImageBlock`s ahead of the `TextBlock(prompt)`; raise on a non-owned/missing ref, on an image to a non-media model, or on an oversized image |

`RunRequest` and the new public assembly name are exported from
`loopplane.webapi.__init__` and documented for the bijection.

### Image media-type detection (pure helper in `uploads.py`)

- `image_media_type(name, data) -> str | None` — returns an image media type
  (e.g. `image/png`, `image/jpeg`, `image/gif`, `image/webp`) when the bytes /
  stored name indicate an image, else `None` (a non-image upload is never guessed
  into an `ImageBlock`). Sniffs the magic bytes first, falls back to the stored
  name's extension; standard library only.

## Validation / behavior rules

- **FR-001/FR-007**: image uploads → leading `ImageBlock`s; non-image uploads →
  **no** block (they remain `read_upload`-readable, 028).
- **FR-004**: an image upload + a non-media model → a normalized error (the web
  layer raises before dispatch); the model never receives image content.
- **FR-006**: an image larger than `max_image_bytes` → a normalized error at the
  conversion point (HTTP 413).
- **FR-008**: a missing or non-owned reference → a clear not-found error (no
  cross-principal read, no existence leak); no run starts with a missing
  attachment.
- **FR-002/FR-003/FR-009**: `loopplane.model.content`, the event schema, the
  `ModelBoundary` Protocol, the Tool Gateway, and the artifact store are
  **unchanged**.
