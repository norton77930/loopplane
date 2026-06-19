# Phase 0 Research: Multimodal Input

The boundary decisions are settled in the ADR (`docs/adr/0001-multimodal-content.md`);
this file records the pre-implementation findings that grounded them.

## Decision 1 — Image input needs NO content-model or event-schema change

- **Decision**: Ship image input by wiring existing pieces at the web edge; do
  **not** touch `loopplane.model.content` or the event envelope/`SCHEMA_VERSION`.
- **Rationale (read of the tree)**:
  - `ImageBlock(kind="image", media, format)` already exists and is part of both
    `OutputBlock` and `ContentBlock` (`src/loopplane/model/content.py`).
  - The model-facing seam already carries arbitrary `ContentBlock`s:
    `Message.blocks: list[ContentBlock]` (`model/boundary.py`),
    `RuntimeController.drive(id, Sequence[ContentBlock])` (`controller/controller.py`),
    and `LoopPlaneHost.run`/`Session.submit` take `Prompt = str | Sequence[ContentBlock]`
    via `_coerce_blocks` (`host/host.py`).
  - The event schema already serializes it: `UserInputEvent.payload.blocks:
    list[ContentBlock]` round-trips an `ImageBlock` through the pydantic
    discriminated-union serde (`tests/contract/test_runtime_events.py`).
  - The Anthropic and OpenAI mappings already emit the provider image wire format
    (`adapters/anthropic/mapping.py` `_image`; `adapters/openai/mapping.py`
    `image_url`); OpenRouter/Ollama (035) reuse the OpenAI mapping unchanged.
- **Alternatives considered**: adding a richer image block / a new block type
  (rejected — unnecessary; the existing block already maps to every supported
  provider and round-trips through the schema).

## Decision 2 — The real gap is the web edge + capability negotiation

- **Decision**: Add (a) an optional `RunRequest.uploads` list of upload references
  resolved into leading `ImageBlock`s, and (b) a capability signal so a text-only
  model degrades gracefully.
- **Rationale**: `RunRequest` carries only `prompt: str` and every run endpoint
  passes only text, so an uploaded image can be *read as text* (028 `read_upload`)
  but never reaches the model as an `ImageBlock`. And nothing tells the host
  whether the selected model accepts images, so an image sent to a text-only model
  fails opaquely at the provider mid-run.

## Decision 3 — Capability is duck-typed + owned by the web/API model-selecting layer

- **Decision**: A model MAY define `accepts_media() -> bool`; a module helper
  `loopplane.model.accepts_media(model)` reads it when present, else returns a
  conservative `False`. The `ModelBoundary` Protocol is **unchanged**. Degradation
  (a normalized HTTP 400) lives at the web/API edge where 028 already resolves
  model selection; the runtime core never negotiates capabilities.
- **Rationale**: Additive + non-breaking (every existing model keeps working);
  matches the house duck-typing style (stream decoders already `getattr` provider
  fields); honors Constitution IV (the loop does not negotiate provider
  capabilities) and V/VI (no gateway/event change). See ADR D5.
- **Alternatives considered**: a required Protocol method (rejected — breaks every
  implementation); enforcement inside the loop/controller (rejected — blurs IV).

## Decision 4 — PDF is deferred (does not map through OpenAI chat-completions)

- **Decision**: Do **not** add a `DocumentBlock`; defer PDF to a follow-up.
- **Rationale**: OpenAI **chat-completions** (the API this repo's OpenAI mapping
  uses, and the one 035's OpenRouter/Ollama reuse) has **no base64 PDF input** —
  multimodal input there is `image_url` only. A `DocumentBlock` is part of the
  versioned event-schema contract (VI); shipping one that silently fails on the
  entire OpenAI-compatible family would break the contract's cross-provider intent.
  PDF also pulls in binary artifact durability (`offload`/`retrieve` are text-only)
  and a non-text gateway handoff — the "deeper rework" 036 is told not to force.
  See ADR D2/D3/D4. Recorded as the recommended follow-up.

## Decision 5 — Offline, deterministic test posture

- **Decision**: Tests use a scripted model + the in-process `TestClient`, a tiny
  real PNG byte string, and a model stub that does / does not implement
  `accepts_media`. No network, no SDK, no live model.
- **Rationale**: Mirrors the 028/035 offline posture; the provider image mappings
  themselves are already covered by unit 020. Any live multimodal check is opt-in
  / secret-gated and out of scope for the gates.
