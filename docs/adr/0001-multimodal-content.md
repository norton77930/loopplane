# ADR 0001: Multimodal content in the conversation model

- **Status**: Accepted (2026-06-19)
- **Deciders**: LoopPlane maintainer; spec 036 (multimodal-input).
- **Supersedes / superseded by**: none. This is the first ADR in the repository.
- **Related**: Constitution **IV** (Runtime Boundary Clarity — a content-model
  change blurs the loop↔model boundary and needs an ADR), **VI** (the Runtime
  Event Bus schema is a versioned, specified, tested contract), **V** (Tool
  Gateway ownership), **VII** (public-safe), **X** (testable + reversible).
  Spec 028 deferred "multimodal/embedded file content" here; spec 035 reused the
  OpenAI mapping for OpenRouter/Ollama, which this ADR depends on.

## Context

Spec 028 added file **attachments** to the web host as *transient input by id*:
an upload is stored as a per-principal blob and the agent reads it **on demand**
as text through the `read_upload` Tool Gateway tool. 028 explicitly deferred
**embedded multimodal content** (placing an image/PDF *into the prompt the model
receives*) to a later unit, on the grounds that it "would touch the content
boundary (Principle IV) and need an ADR." Spec 036 is that unit.

A pre-implementation read of the tree established that the conversation content
model is already **most of the way** to embedded image input:

- `loopplane.model.content` already defines `ImageBlock(kind="image", media,
  format)` and includes it in both `OutputBlock` and `ContentBlock`.
- The model-facing seam already carries it end to end:
  `Message.blocks: list[ContentBlock]`; `RuntimeController.drive(id,
  Sequence[ContentBlock])`; `LoopPlaneHost.run`/`Session.submit` take
  `Prompt = str | Sequence[ContentBlock]` (`_coerce_blocks`).
- The event schema already serializes it losslessly:
  `UserInputEvent.payload.blocks: list[ContentBlock]` round-trips an `ImageBlock`
  (a base64 string) through the pydantic discriminated-union serde
  (`tests/contract/test_runtime_events.py`).
- The Anthropic and OpenAI mappings already emit the provider image wire format
  (`adapters/anthropic/mapping.py`, `adapters/openai/mapping.py`); OpenRouter and
  Ollama (035) reuse the OpenAI mapping, so they inherit image support.
- The Tool Gateway SPI already admits images as tool *output*
  (`AdapterOutput = TextBlock | ImageBlock | ErrorOutput`); the MCP adapter
  already emits `ImageBlock` from a server's image content.

So the genuinely missing pieces for *image input* are **not** in the content
model. They are:

1. **The web edge.** `RunRequest` carries only `prompt: str`; the run endpoints
   (`/v1/runs`, `/v1/runs/events`, `/v1/sessions/{id}/submit`) pass only text, so
   an uploaded image can be *read as text* (028) but never reaches the model as
   an `ImageBlock`.
2. **Capability negotiation.** Nothing tells the host whether the selected model
   can accept images, so sending an image to a text-only model would fail
   opaquely at the provider instead of degrading with a clear, normalized error.
3. **A media size cap** at the point an upload becomes an `ImageBlock`.

The open *questions* this ADR must settle are the ones spec 028 flagged as
"needs an ADR":

- **PDF** representation — a new `DocumentBlock`, an `ImageBlock`-per-page, or
  defer?
- **Binary durability** — should embedded media or oversized binary tool output
  be inlined as base64 or offloaded to the artifact store as a reference (the
  `ArtifactStore.offload`/`retrieve` path is text-only today)?
- **The gateway non-text oversized-output path** — today's artifact handoff and
  truncation are text-shaped.
- **Provider capability negotiation** — the `accepts_media`-style signal and the
  graceful-degradation behavior.
- **Size / budget caps** for media.

## Decision

### D1 — Image input ships now as an **additive** increment; the content model and event schema are **unchanged**.

Because `ImageBlock` already exists in `ContentBlock`/`OutputBlock` and already
round-trips through the event schema and both provider mappings, image input
requires **no change to `loopplane.model.content`, no change to the event
envelope/schema, and no `SCHEMA_VERSION` bump**. 036 wires the existing pieces
together at the web edge and adds capability negotiation. This keeps the
loop↔model boundary (IV) and the event-bus contract (VI) intact: the only new
data that crosses the bus is an `ImageBlock` the schema *already* admits, and the
existing round-trip test is extended to assert an `ImageBlock`-bearing
`UserInputEvent` is lossless (VI: a content-block change must be tested — here we
prove the *existing* block is contract-safe on the input path).

### D2 — PDF is **deferred** to a follow-up; **no `DocumentBlock` is added**.

A `DocumentBlock(kind="document", media, format="application/pdf")` would be
syntactically symmetric with `ImageBlock` for `content.py`, the SPI
`AdapterOutput`, sizing, and serde, and it would map cleanly to **Anthropic**
(`{"type":"document","source":{"type":"base64",
"media_type":"application/pdf","data": …}}`). It is **not** cleanly additive
across the providers this sprint just unified, for two reasons:

- **OpenAI chat-completions has no base64-PDF input.** The OpenAI mapping this
  repo uses is the **chat-completions** API, whose multimodal input is
  `image_url` only; base64 PDF input is an OpenAI *Responses*-API / Files-API
  feature, not chat-completions. So a `DocumentBlock` would **silently fail on
  the entire OpenAI-compatible family** (OpenAI **and** the OpenRouter/Ollama
  providers that 035 unified by reusing the chat-completions mapping). Shipping a
  content block that is part of the **versioned event-schema contract (VI)** but
  works on only one of the supported providers would violate the contract's
  "works across the supported surface" intent and create an asymmetry the event
  schema is supposed to prevent.
- **Binary durability is entangled.** PDFs are large and commonly arrive as tool
  *output*, not just user input. The artifact path that should preserve them
  (`ArtifactStore.offload`/`retrieve`) is **text-only today** (`offload` joins
  only `TextBlock`s and writes a `.txt`; `retrieve` returns `str`), and the
  gateway's oversized-output handoff/truncation (`gateway/sizing.py`,
  `ToolGateway._run_one`) is text-shaped. Doing PDF *properly* therefore pulls in
  binary artifact durability and a non-text gateway handoff — exactly the
  "deeper rework" 036 is instructed not to force.

Per Constitution X (incremental over big-bang) and the spec-036 mandate to "be
rigorous and conservative — prefer a reliable, additive image-input increment +
a thorough ADR over an over-reaching change," PDF is **deferred**. It is recorded
as the recommended follow-up (see Consequences → Follow-ups) with the exact shape
it should take once binary durability lands.

### D3 — Binary durability in the artifact store is a **documented follow-up**; `store.py` is **unchanged** in 036.

`ArtifactStore` already *declares* `media_kind: Literal["text","image","binary"]`
in `ArtifactMeta`, but `offload()` hardcodes `"text"` and `retrieve()` returns
`str`. Image **input** does **not** flow through the artifact store (it is a user
*input* block, not oversized tool *output*), so 036 needs no change here. A
binary-capable `offload`/`retrieve` (write the raw bytes + a real `media_kind`;
`retrieve_bytes`) is the prerequisite for the deferred PDF/binary-output work and
is recorded as a follow-up. Leaving it untouched keeps 036 surgical and
reversible.

### D4 — The gateway non-text oversized-output path is a **documented follow-up**; the gateway is **unchanged** in 036.

When a tool returns oversized output containing an `ImageBlock`, the current
handoff offloads only the text and the truncation path keeps whole image blocks
until the byte budget — a pre-existing limitation about tool **output**, orthogonal
to image **input** (036's primary goal). It is bundled with the D3 binary-durability
follow-up (a binary `offload` is the natural place to fix it). Not touching the
gateway here honors V (no new gateway stage, no behavior change) and keeps the
diff small.

### D5 — Provider capability negotiation: an **optional, duck-typed `accepts_media` signal** + **graceful normalized degradation** at the model-selecting boundary.

- **The signal.** A model boundary MAY advertise media support by defining
  `accepts_media() -> bool`. A new module-level helper
  `loopplane.model.accepts_media(model) -> bool` reads `model.accepts_media()`
  when present and otherwise returns a **conservative `False`**. This is
  **additive and non-breaking**: the `ModelBoundary` Protocol is **unchanged**
  (still `stream_turn` + `context_capacity`), so every existing implementation
  (`ScriptedModel`, `AnthropicModel`, `OpenAIModel`, the CLI `DemoModel`) keeps
  working. It matches the house duck-typing style (the stream decoders already
  consume providers via `getattr`). The two real adapters opt in via a config
  flag (`AnthropicConfig.accepts_media`, `OpenAIConfig.accepts_media`, default
  `True` — both flagship families are vision-capable today); `openrouter_model`
  defaults `True` (it brokers vision models) and `ollama_model` defaults `False`
  (local models are commonly text-only; the operator opts in).
- **Degradation.** The web/API layer **owns model selection** (028: per-session
  selection is resolved in the web/API layer; the runtime still gets one model
  per run). So the web edge is where degradation lives: when a turn carries image
  attachments and the selected model does **not** accept media, the request is
  rejected with a clear, public-safe normalized error (HTTP 400,
  `ErrorResponse(detail="selected model does not accept image input")`) **before**
  any unsupported content is dispatched — never a silent wrong-content run. The
  model catalog (`/v1/models`) advertises `accepts_media` per model so a client
  can hide the attach affordance for text-only models. For non-web embedders
  (CLI/desktop/direct), the same helper is available to gate input; the runtime
  core is deliberately **not** made to police this (it would blur IV — the loop
  does not negotiate provider capabilities).

### D6 — Size / budget cap for embedded media.

The upload store already caps a stored blob (028, default 5 MiB). 036 adds a
second, explicit cap at the **conversion point** (upload → `ImageBlock`): a
configurable `max_image_bytes` (default 5 MiB) on the web app; an image upload
larger than the cap is rejected with a normalized error (HTTP 413) rather than
embedded. This bounds the base64 payload that enters the context and the event
stream. (A token-cost budget for media is out of scope — pricing is deferred,
per 028/029.)

## Consequences

### Positive

- **Smallest correct change.** Image input — the high-value, reliable
  increment — ships by wiring existing, already-tested pieces at the web edge,
  with **zero change to the content model or the event schema** and no
  `SCHEMA_VERSION` bump. The parent's content-model review surface is therefore
  *empty*: there is nothing new in `content.py` or the event envelope to audit.
- **Graceful degradation.** A text-only model can no longer be sent an image
  silently; it returns one clear normalized error, and the catalog advertises the
  capability so UIs adapt.
- **OpenRouter/Ollama inherit image input for free** (035 reused the OpenAI
  mapping), so this single unit lights up image input across Anthropic, OpenAI,
  OpenRouter, and (vision-capable) Ollama models.
- **Reversible (X).** Removing the new `RunRequest.uploads` field + the webapi
  image-assembly helper + the `accepts_media` flags restores the prior text-only
  behavior; nothing in the runtime core or the schema changed.

### Negative / trade-offs

- **No PDF yet.** Users who want PDF-to-model must, for now, rely on the 028
  `read_upload` tool (text extraction on demand) rather than embedded document
  content. This is an accepted, documented limitation (D2).
- **`accepts_media` defaults are heuristic.** Defaulting Anthropic/OpenAI to
  `True` is correct for current flagship models but could be wrong for a
  hypothetical text-only model on those families; the flag is configurable so an
  operator can correct it. The conservative `False` default of the *helper* (when
  a model doesn't implement the method at all) means a custom `ModelBoundary` is
  assumed text-only until it opts in — a safe default.

### Follow-ups (recommended, not in 036)

1. **Binary artifact durability** — make `ArtifactStore.offload` write raw bytes
   with a real `media_kind` and add `retrieve_bytes`; teach the gateway
   oversized-output handoff/truncation to handle non-text blocks (D3 + D4).
2. **`DocumentBlock` / PDF** — once (1) lands, add `DocumentBlock` with: an
   Anthropic base64-document mapping; for the OpenAI-compatible family, either an
   OpenAI **Responses/Files**-API path or a documented fallback (e.g. server-side
   text extraction routed through the existing text path) so the block degrades
   instead of silently failing (D2).
3. **Native Gemini** — a separate deferred follow-up from spec 035 (direct Google
   GenAI API + `thought_signature`); unrelated to this ADR but tracked alongside.

## Alternatives considered

- **Add `DocumentBlock` now (ship image + PDF).** Rejected: PDF does not map
  through OpenAI chat-completions and pulls in binary artifact durability + a
  non-text gateway handoff; shipping a contract-level content block that works on
  only one provider violates the event-schema contract's intent (VI) and is the
  over-reaching change 036 was told to avoid (D2).
- **Add `accepts_media` to the `ModelBoundary` Protocol as a required method.**
  Rejected: it breaks every existing implementation and many tests for no benefit
  over an additive duck-typed helper; the optional helper is non-breaking and
  matches the codebase's duck-typing convention (D5).
- **Enforce capability negotiation inside the Agent Loop / Controller.**
  Rejected: the loop does not negotiate provider capabilities; doing so blurs the
  runtime boundary (IV). The web/API layer already owns model selection (028), so
  degradation belongs there; the helper is exposed for other embedders (D5).
- **Inline media into the artifact store / treat an embedded image as an
  artifact.** Rejected for input: a user-supplied image is *input*, not oversized
  *output*; routing it through the artifact store would conflate two boundaries.
  Binary durability is still recorded as a follow-up for the *output* path (D3).
- **Embed images with no size cap.** Rejected: an unbounded base64 payload would
  bloat the context and the event stream; D6 adds an explicit conversion-point
  cap.
