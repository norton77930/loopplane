# Feature Specification: Multimodal Input (Image Attachments to the Model)

**Feature Branch**: `036-multimodal-input` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Multimodal input (the largest, most invasive Tier-1
unit, carrying a narrowed ADR). Image content is ~80% already wired through the
runtime; the gap is connecting the existing upload path so an uploaded image
becomes an `ImageBlock` the model receives, plus provider capability negotiation
so a non-image model degrades gracefully. PDF (a `DocumentBlock`), binary artifact
durability, and the gateway non-text-output handoff are settled by an ADR
(`docs/adr/0001-multimodal-content.md`): ship image input now; defer PDF/binary
as a documented follow-up because PDF does not map through OpenAI
chat-completions. Native Gemini is a separate deferred follow-up from spec 035."

## Overview

The runtime already models image content: `ImageBlock` is part of both
`ContentBlock` and `OutputBlock`; the model-facing seam (`Message.blocks`,
`RuntimeController.drive`, `LoopPlaneHost.run`/`Session.submit` over
`Prompt = str | Sequence[ContentBlock]`) already carries it; the event schema
(`UserInputEvent.payload.blocks`) already serializes it losslessly; and the
Anthropic and OpenAI mappings already emit the provider image wire format —
OpenRouter and Ollama (035) inherit it by reusing the OpenAI mapping. What is
missing is **not** the content model.

Spec 028 added file **attachments** as transient input the agent reads *as text*
on demand (the `read_upload` Tool Gateway tool), and explicitly **deferred
embedded multimodal content to a later unit needing an ADR**. This unit is that
follow-up. It delivers, additively:

1. **Image input end-to-end at the web edge** — a run/turn may reference one or
   more uploaded files; each upload that is an image is assembled into an
   `ImageBlock` and prepended to the user message the model receives (the text
   prompt follows). Non-image uploads remain available to the `read_upload` tool
   exactly as in 028 (unchanged).
2. **Provider capability negotiation** — a model may advertise
   `accepts_media()`; a model-selecting boundary degrades **gracefully** (a clear
   normalized error, never a silent wrong-content run) when image input is sent to
   a text-only model, and the model catalog advertises the capability.
3. **A media size cap** at the conversion point (upload → `ImageBlock`).

A **narrowed ADR** (`docs/adr/0001-multimodal-content.md`, the repo's first)
settles the boundary questions: **image input ships now with NO content-model or
event-schema change**; **PDF (a `DocumentBlock`) is deferred** because it does not
map through OpenAI chat-completions and would pull in binary artifact durability
and a non-text gateway handoff (the "deeper rework" this unit is told not to
force). Native Gemini remains a separate deferred follow-up from spec 035.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Send an uploaded image to the model (Priority: P1)

A user uploads an image (the existing `POST /v1/uploads`, 028), then sends a turn
that references the upload. The agent's model receives the image as an `ImageBlock`
alongside the text prompt, so the model can actually see the picture — not merely
read its bytes as text.

**Why this priority**: This is the unit's reason to exist — turning the
already-modeled `ImageBlock` into a capability a user can actually reach from the
web host, across every provider that supports vision (Anthropic, OpenAI, and the
035 OpenAI-compatible family).

**Independent Test**: With an uploaded image reference, post a run that carries it;
assert the user message the runtime received contains an `ImageBlock` whose
`media`/`format` match the upload, ahead of the text — verified offline with a
scripted model and an in-process client.

**Acceptance Scenarios**:

1. **Given** an uploaded image reference, **When** a run/turn carries it and the prompt text, **Then** the user message the model receives contains an `ImageBlock` (the image) followed by the `TextBlock` (the prompt).
2. **Given** an uploaded **non-image** reference (e.g. a `.txt`), **When** a run carries it, **Then** no `ImageBlock` is fabricated for it (it stays a `read_upload`-readable attachment, 028 behavior unchanged).
3. **Given** an upload reference that does not exist or is not owned by the caller, **When** a run carries it, **Then** the request is rejected with a clear normalized error and no run starts with a missing attachment.

### User Story 2 - A text-only model degrades gracefully (Priority: P1)

A user has selected a text-only model and tries to send an image. Instead of a
silent failure or an opaque provider error mid-run, they get a clear message that
the chosen model cannot accept images; the catalog already told the UI which
models accept images.

**Why this priority**: Without negotiation, an image sent to a text-only model
fails opaquely at the provider after the run starts. Graceful degradation is a
correctness requirement, not a nicety.

**Independent Test**: Build a model that does not advertise media support; post a
run carrying an image; assert a clear normalized error (HTTP 400) and that the
model never received image content. Assert the catalog reports `accepts_media`
per model.

**Acceptance Scenarios**:

1. **Given** a selected model that does not accept media, **When** a run carries an image upload, **Then** the request is rejected with a clear, public-safe normalized error and no image is dispatched.
2. **Given** the model catalog, **When** it is listed, **Then** each entry reports whether it `accepts_media`, so a client can adapt the attach affordance.
3. **Given** a model that does accept media, **When** a run carries an image, **Then** the image is dispatched normally (US1).

### Edge Cases

- **Image larger than the media cap** → rejected with a normalized error (HTTP 413) at the conversion point, not embedded (the base64 payload is bounded).
- **Multiple uploads on one turn** → each image becomes an `ImageBlock` in reference order, all ahead of the text prompt; mixed image/non-image lists keep only the images as blocks.
- **A reference owned by another principal** → treated as not found (no cross-principal read, no existence leak — 022/028 posture).
- **No uploads on a turn** → identical to the prior text-only path (a single `TextBlock`); the new field is optional and defaults empty.
- **A model that doesn't implement `accepts_media()` at all** → treated as text-only (a conservative `False` default), so a custom model is never sent unsupported content until it opts in.
- **PDF / non-image binary uploaded as an "image"** → not assembled into an `ImageBlock` (only image media types are embedded); it remains a `read_upload` attachment. (Embedded PDF is deferred — ADR D2.)
- **Image format detection** → the media type is taken from the upload (its stored name's extension / recorded type); an undetectable type is treated as a non-image attachment, never guessed into an `ImageBlock`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A run/turn over the web host MUST be able to carry one or more **upload references**, and each referenced upload that is an **image** MUST be assembled into an `ImageBlock` placed in the user message **ahead of** the text prompt (Constitution VI: the `ImageBlock` already in the event schema now reaches the model on the input path; no schema change).
- **FR-002**: The content model (`loopplane.model.content`) and the runtime event schema (`SCHEMA_VERSION`, the event envelope) MUST be **unchanged** — image input reuses the existing `ImageBlock`/`ContentBlock`/`UserInputEvent.blocks` (ADR D1; Constitution IV/VI).
- **FR-003**: A model boundary MAY advertise media support via `accepts_media()`; a non-advertising model MUST be treated as text-only (a conservative default). The `ModelBoundary` Protocol MUST stay **unchanged** (additive duck-typed helper, not a new required method — Constitution IV; ADR D5).
- **FR-004**: When a run carries image input and the selected model does **not** accept media, the request MUST be rejected with a clear, public-safe **normalized error** (never a silent wrong-content run, never a raw provider error). Capability negotiation MUST live at the **web/API model-selecting boundary** (028 owns model selection there); the runtime core/Agent Loop MUST be **unchanged** (Constitution IV/V/VI; ADR D5).
- **FR-005**: The model catalog (`/v1/models`) MUST advertise `accepts_media` per model so a client can adapt the attach affordance (FR-005 of 028 extended additively).
- **FR-006**: An image upload larger than a configurable **media size cap** MUST be rejected with a normalized error at the conversion point (upload → `ImageBlock`) rather than embedded, bounding the base64 payload entering the context/event stream (ADR D6).
- **FR-007**: A non-image upload MUST remain a transient `read_upload` attachment exactly as in 028 (read as text on demand) — never fabricated into an `ImageBlock`; embedded **PDF/`DocumentBlock`** is **out of scope / deferred** (ADR D2).
- **FR-008**: Upload references on a turn MUST honor the existing **auth/per-principal** boundary (022/028): a missing or non-owned reference is a clear not-found error and no run starts with a missing attachment (Constitution VII).
- **FR-009**: The artifact store (`offload`/`retrieve`) and the gateway oversized-output handoff MUST be **unchanged** in this unit; binary durability and the non-text handoff are the ADR's recommended **follow-up** (ADR D3/D4; Constitution V/X).
- **FR-010**: The change MUST be **additive and reversible**: removing the run-request upload field, the image-assembly helper, and the `accepts_media` flags restores the prior text-only behavior with no runtime-core or schema change (Constitution X).
- **FR-011**: Any new public name MUST keep the unit-014 api-reference bijection green (documented 1:1 against the owning package `__all__`), and no committed artifact may carry a secret, key, private path, or internal name (Constitution VII).

### Key Entities

- **Upload reference on a turn**: an optional list of upload ids the run/turn carries (`RunRequest.uploads`); each is resolved through the existing per-principal `UploadStore` (028).
- **Image assembly helper**: a small, pure web-layer function that turns resolved uploads into the user message's leading `ImageBlock`s (images only), detecting the media type from the stored upload; non-images are skipped.
- **`accepts_media(model)` helper** (`loopplane.model`): reads `model.accepts_media()` when present, else `False` — the additive capability probe.
- **`accepts_media` config flag**: on `AnthropicConfig`/`OpenAIConfig` (default `True`); the `openrouter_model` (default `True`) / `ollama_model` (default `False`) constructors expose it.
- **Catalog capability**: `ModelHost.accepts_media` + `ModelInfo.accepts_media` so `/v1/models` advertises it.

## Out of Scope

- **PDF / embedded `DocumentBlock`** — deferred (ADR D2): PDF does not map through OpenAI chat-completions and would require binary artifact durability + a non-text gateway handoff. Non-image files remain `read_upload`-readable (028).
- **Binary artifact durability** (`ArtifactStore` raw-bytes `offload`/`retrieve`) and the **gateway non-text oversized-output handoff** — the ADR's recommended follow-up (D3/D4); untouched here.
- **Native Gemini adapter** (direct Google GenAI API + `thought_signature`) — a separate deferred follow-up from spec 035; reachable via OpenRouter today.
- **Any change to the runtime core, the Agent Loop, the content model, the event schema, or the Tool Gateway execution path.**
- **A frontend change** — the web composer already uploads files (028); surfacing image attachments in the SPA is a follow-on frontend task. This unit delivers the **backend** capability + the catalog signal a frontend would read.
- **Token-cost budgeting for media / server-side pricing** — deferred (028/029).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An uploaded image referenced on a run reaches the model as a leading `ImageBlock` (verified offline against a scripted model + in-process client); the text prompt follows.
- **SC-002**: A run carrying an image against a text-only model is rejected with a clear normalized error and dispatches no image; the catalog reports `accepts_media` per model.
- **SC-003**: The content model and the runtime event schema are **unchanged** — `SCHEMA_VERSION` is unchanged and the existing serde round-trip (now asserted for an `ImageBlock`-bearing `UserInputEvent`) stays lossless (Constitution VI).
- **SC-004**: An oversized image upload is rejected at the conversion point; non-image uploads remain `read_upload`-readable (028 unchanged).
- **SC-005**: The four quality gates stay green, including the unit-014 api-reference bijection for any new public name; the prior Python suite count plus the new tests pass.

## Assumptions

- **Image content is already modeled and contract-safe.** `ImageBlock` is in
  `ContentBlock`/`OutputBlock`, round-trips through the event schema, and maps to
  Anthropic/OpenAI (OpenRouter/Ollama inherit via the OpenAI mapping). So image
  input is an **additive wiring** at the web edge, not a content-model change
  (ADR D1).
- **The web/API layer owns model selection** (028), so capability degradation
  belongs there; the runtime core is never made to negotiate provider
  capabilities (Constitution IV).
- **PDF is genuinely not cleanly additive** across the unified OpenAI-compatible
  family (no base64 PDF in chat-completions), so deferring it is the conservative,
  contract-respecting choice (ADR D2; Constitution VI/X).
- **Additive, reversible** — removing the new field/helpers/flags restores the
  prior behavior; units 020/028/035 are otherwise untouched (Constitution X).
