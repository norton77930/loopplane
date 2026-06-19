# Feature Specification: Native Google Gemini Model-Provider Adapter

**Feature Branch**: `037-gemini-adapter` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "The deferred 035 follow-up: a NATIVE Google Gemini adapter at the existing model boundary (direct Google GenAI SDK, not via the OpenAI-compatible OpenRouter path). Add `loopplane.adapters.gemini` behind a new optional `gemini` extra, lazily importing the official Google GenAI SDK, mapping Gemini's `contents`/`tools`/streaming-chunk shape to the loop's normalized increments (text, reasoning, raw tool calls, usage), with offline stub tests. Be conservative with the shared content model — default to documenting the multi-turn `thought_signature` limitation rather than changing the content model; only change it with an ADR + serde tests + a prominent flag, and only if Gemini hard-fails without it."

## Overview

The runtime ships three real model integrations behind the existing model
boundary: Anthropic and OpenAI (unit 020, each a full adapter behind its own
optional extra) and the OpenAI-compatible providers OpenRouter + Ollama
(unit 035, thin `base_url` wrappers reusing the OpenAI adapter). Spec 035
explicitly **deferred a native Gemini adapter** (its research Decision 2) on the
grounds that it needs the Google GenAI SDK behind a new extra and careful
`thought_signature` handling across multi-turn tool use — and that Gemini is
already reachable via OpenRouter in the meantime.

This unit ships that deferred native adapter. It adds a new public package
`loopplane.adapters.gemini` — `GeminiConfig` + `GeminiModel` + a request/stream
mapping — behind a new optional extra **`gemini`** (the official **`google-genai`**
SDK). Exactly like the unit-020 Anthropic/OpenAI adapters, the SDK is imported
**lazily** inside the client factory, the provider stream is consumed by
**duck-typing**, and the whole adapter is tested **offline with a stub client**, so
the package imports without the extra and the default gates need no SDK and no
network. The adapter implements the **unchanged** `ModelBoundary` (`stream_turn`,
`context_capacity`) plus the additive duck-typed `accepts_media()` signal
(unit 036; Gemini is vision-capable → `True`), so it registers as a `/v1/models`
host like every other adapter with **no frontend change**.

A native adapter (vs OpenRouter) is justified because Gemini's wire format is
**not** OpenAI chat-completions — it has its own `contents`/`parts` request shape,
`function_declarations` tool shape, `inline_data` image shape, and
`usage_metadata` accounting — and because the direct API exposes Gemini-specific
signals (thinking parts, the per-`function_call` `thought_signature`) that the
OpenAI-compatible broker flattens away.

### The `thought_signature` decision (conservative — content model UNCHANGED)

Gemini attaches a per-`function_call` **`thought_signature`** (an encrypted
representation of the model's reasoning) that the API expects echoed back on the
next turn. For **Gemini 3** models, omitting it on the first `function_call` part
of the current turn is a **hard 400 error** (Gemini 2.5 produces it optionally and
does not require it). The shared content model (`ToolCallBlock`) has **no field**
for it, and ADR 0001 deliberately kept the content model unchanged.

Crucially, Google provides an **official, documented escape hatch**: a function
call sent back with a sentinel `thought_signature` of
`"skip_thought_signature_validator"` **skips validation**. So multi-turn tool use
can be made to **work** against Gemini 3 **without** adding a field to the shared
content model: when this adapter re-maps a prior `ToolCallBlock` (which carries no
signature), it attaches that official sentinel to the outgoing `function_call`
part.

Therefore this unit takes the **conservative path the brief prefers**:

- **The content model and the event schema are UNCHANGED** (no new field on
  `ToolCallBlock`, no `SCHEMA_VERSION` bump; ADR 0001 D1 philosophy preserved).
- Text, streaming, vision, usage, and **single-turn and multi-turn tool use** all
  work — multi-turn via the official `skip_thought_signature_validator` sentinel.
- The **documented limitation** is one of *reasoning continuity quality, not
  function*: because the real per-call signature is not preserved across turns (it
  has nowhere to live in the shared model), Gemini's cross-turn reasoning chain may
  degrade slightly relative to a client that round-trips the genuine signature.
  **Full real-signature preservation would need a content-model field — a
  Constitution VI / ADR matter — and is recorded as a deferred follow-up.**

This unit does **not** change the content model. (Had Gemini hard-failed
multi-turn tool use with *no* official bypass, the brief's "ONLY IF" path — an
additive optional `ToolCallBlock` field + ADR 0002 + serde round-trip/sizing
tests + a prominent flag — would have applied; it does not, because the bypass
exists.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drive a text + streaming run through native Gemini (Priority: P1)

An embedder configures a Gemini-backed model host (a model id + an injected Google
API key) and the agent loop streams a turn against the direct Google GenAI API,
producing the same normalized increments (`TextIncrement` … `TurnEnd` with usage)
the loop already consumes from the other adapters.

**Why this priority**: Text + streaming + usage is the core boundary obligation
and the highest-value, most-used path; it must be correct first.

**Independent Test**: Drive `GeminiModel.stream_turn` with a stub client that
yields Gemini-shaped streaming chunks (text parts + a `usage_metadata`) and assert
the ordered normalized increments (`TextIncrement`(s) → one `TurnEnd` with the
mapped token usage).

**Acceptance Scenarios**:

1. **Given** a Gemini model + an injected key, **When** the loop streams a text turn, **Then** the adapter yields `TextIncrement`s followed by exactly one `TurnEnd` whose `usage` carries Gemini's `prompt_token_count` / `candidates_token_count` (and cached/thoughts counts when present).
2. **Given** the `google-genai` SDK is not installed, **When** the package is imported, **Then** it imports successfully (the SDK is imported only inside the client factory); an injected client bypasses the factory entirely for offline tests.

### User Story 2 - A tool-using turn surfaces a raw tool call (Priority: P1)

A Gemini turn that emits a `function_call` part is mapped to a raw
`ToolCallRequest` (call id, tool name, the args dict passed through **raw**), which
the Tool Gateway then validates — exactly as for the other adapters
(Constitution V).

**Why this priority**: Tool use is the second core boundary obligation; the
gateway owns validation, so the adapter must surface the call **unvalidated**.

**Independent Test**: Drive the decoder with a stub stream containing a
`function_call` part (name + args) and assert a single `ToolCallRequest` with the
raw args dict, plus one `TurnEnd`. Build the request contents from a prior
`ToolCallBlock` + `ToolResultBlock` and assert the Gemini `function_call` /
`function_response` parts (and that the re-mapped `function_call` carries the
`skip_thought_signature_validator` sentinel so multi-turn does not 400).

**Acceptance Scenarios**:

1. **Given** a Gemini turn with a `function_call` part, **When** the stream is decoded, **Then** the adapter emits a `ToolCallRequest(call_id, tool_name, input)` with the args passed through raw (no adapter-side validation) and then one `TurnEnd`.
2. **Given** a context containing a prior assistant `ToolCallBlock` and a user `ToolResultBlock`, **When** the request `contents` are built, **Then** they contain a `model`-role `function_call` part and a `user`-role `function_response` part, and the re-mapped `function_call` carries `thought_signature = "skip_thought_signature_validator"` (the official multi-turn bypass; no real signature is invented).

### User Story 3 - Vision input maps to inline image data (Priority: P2)

A user message containing an `ImageBlock` is mapped to a Gemini `inline_data` part
(base64 data + mime type), so an image reaches the vision-capable model; the
adapter advertises `accepts_media() == True`.

**Why this priority**: Gemini is vision-capable and unit 036 shipped image input
end-to-end; the native adapter must carry it (and advertise it for the
`/v1/models` capability signal) to be at parity with the other adapters.

**Independent Test**: Build the request `contents` from a message containing an
`ImageBlock` and assert an `inline_data` part with the base64 data + mime type;
assert `GeminiModel(...).accepts_media()` is `True` and `accepts_media(model)` is
`True`.

**Acceptance Scenarios**:

1. **Given** a user message with an `ImageBlock(media, format)`, **When** the `contents` are built, **Then** they contain an `inline_data` part carrying that base64 data and mime type.
2. **Given** a default Gemini model, **When** `accepts_media()` is probed, **Then** it returns `True`; **When** the config sets `accepts_media=False`, **Then** the probe returns `False`.

### Edge Cases

- **Context overflow** → a Gemini context-too-long / resource-exhausted signal is normalized to `ContextOverflowError`, so the loop can compact and retry exactly once (FR-008 of the runtime).
- **Provider / transport / credential error** → normalized to the shared `ModelProviderError` with a public-safe message; **no key, no raw SDK/response body leaks** (Constitution VII), matching the unit-020 adapters.
- **Missing `gemini` extra** → the package still imports (the SDK is imported only inside the client factory); offline tests inject a stub client and never import the SDK.
- **Reasoning / thinking parts** → a thought/thinking part, when present, is mapped to a `ReasoningIncrement`; absent thinking, the path degrades gracefully (no reasoning increments).
- **Multi-turn tool use** → works via the official `skip_thought_signature_validator` sentinel; full *real* `thought_signature` preservation is a documented, deferred limitation (would need a content-model field — VI/ADR).
- **Registry listing** → the adapter registers as a model host the same way the other adapters do, so `/v1/models` lists it with no UI change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unit MUST add a native Google Gemini adapter (`loopplane.adapters.gemini`) implementing the existing `ModelBoundary` (`stream_turn`, `context_capacity`) over the **direct** Google GenAI API (the official `google-genai` SDK), distinct from the OpenAI-compatible OpenRouter path (035).
- **FR-002**: The SDK MUST be imported **lazily** (only inside the client factory), so the package imports **without** the `gemini` extra installed; the config MUST accept an injected `client` (and a `client_factory`) so offline tests need no SDK and no network (mirrors unit 020).
- **FR-003**: `stream_turn` MUST build the Gemini request (`contents` + `tools`) from the `ModelRequest`, call the SDK's **async streaming** generate, and map the chunk stream to the loop's normalized increments: text parts → `TextIncrement`; thought/thinking parts → `ReasoningIncrement` (when present); `function_call` parts → an accumulated raw `ToolCallRequest`; `usage_metadata` → `TokenUsage`; ending with exactly one `TurnEnd`.
- **FR-004**: Tool calls MUST surface as **raw** `ToolCallRequest`s (call id, tool name, args dict passed through unmodified); the adapter MUST NOT validate tool input — the Tool Gateway owns validation (Constitution V).
- **FR-005**: The request mapping MUST translate the conversation content blocks to Gemini parts — `TextBlock` → text, `ImageBlock` → `inline_data` (base64 + mime type), `ToolCallBlock` → a `model`-role `function_call`, `ToolResultBlock` → a `user`-role `function_response`, `SummaryMarkerBlock` → text — and `ToolDescriptor`s to Gemini `function_declarations`.
- **FR-006**: A Gemini context-overflow signal MUST be normalized to `ContextOverflowError`; every other provider/transport/credential failure MUST be normalized to the shared `ModelProviderError` with a **public-safe** message that leaks **no key and no raw SDK/response body** (Constitution VII).
- **FR-007**: The adapter MUST advertise `accepts_media()` (unit 036; ADR 0001 D5), defaulting to `True` (Gemini is vision-capable), overridable via the config; the `ModelBoundary` Protocol MUST remain unchanged (the signal is the additive duck-typed one).
- **FR-008**: The shared **content model and the event schema MUST remain UNCHANGED** — no new field on `ToolCallBlock`, no `SCHEMA_VERSION` bump. Multi-turn tool use MUST be made functional by attaching Google's official `"skip_thought_signature_validator"` sentinel when re-mapping a prior `ToolCallBlock`; the adapter MUST NOT invent a fake signature value and MUST NOT smuggle non-argument data into the tool-input dict the gateway validates.
- **FR-009**: The unit MUST add a new optional extra **`gemini`** in `pyproject.toml` (the official `google-genai` package) and MUST add **no required** runtime dependency; the core install MUST still import the package.
- **FR-010**: The new public package MUST declare `__all__` and be documented in `docs/api-reference.md` so the unit-014 reference bijection stays green.
- **FR-011**: The adapter MUST register as a model host the same way the other adapters do, so the existing `/v1/models` registry and UI selector surface it with **no frontend change**.
- **FR-012**: The unit MUST be covered by **deterministic offline tests** (a Gemini-shaped stub client + stand-in chunks): ordered normalized increments, a raw tool-call round-trip, vision (`ImageBlock` → `inline_data`), context-overflow → `ContextOverflowError`, error/credential non-leakage, and `accepts_media()` `True`. Any live-model check MUST be opt-in / secret-gated and excluded from the default gates.

### Key Entities

- **`GeminiConfig`**: declarative configuration for `GeminiModel` — `model`, `context_capacity` (Gemini windows are large), `max_output_tokens`, `api_key`, `client`, `client_factory`, `accepts_media` (default `True`). Carries no committed secret; the credential is injected.
- **`GeminiModel`**: a `ModelBoundary` over the Google GenAI async streaming API — `stream_turn`, `context_capacity`, `accepts_media`.
- **`build_contents(context)`**: maps the loop's `Message`/`ContentBlock` list to Gemini `contents` (roles `user`/`model`; text / `inline_data` / `function_call` / `function_response` parts).
- **`build_tools(tools)`**: maps `ToolDescriptor`s to a Gemini `tools` list of `function_declarations`.
- **`GeminiStreamDecoder`**: turns the Gemini chunk stream into ordered normalized increments (text/reasoning/tool-call) and one `TurnEnd` carrying the mapped `TokenUsage`.

### Out of Scope

- **Any change to the shared content model or the event schema** — `ToolCallBlock` gains no signature field and `SCHEMA_VERSION` is not bumped (the conservative path; full real-`thought_signature` preservation is a deferred VI/ADR follow-up).
- **Automatic function calling / the SDK's tool-execution loop** — the runtime owns the loop and the Tool Gateway owns execution (V); the adapter only maps requests/streams.
- **Gemini-specific generation knobs** beyond model / max-output-tokens / tools (e.g. safety-setting tuning, JSON-schema response mode, grounding/search tools) — not needed for boundary parity.
- **Server-side key management** — the key is injected by the host, never committed.
- **A guaranteed-resolvable `google-genai` install in the offline gates** — if the SDK cannot be resolved offline, the import stays lazy + the extra declared and the offline stub tests carry the unit (exactly as unit 020 does for its providers).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A native Gemini model can be built with a model id + an injected key, and `stream_turn` yields ordered `TextIncrement`s → one `TurnEnd` with the mapped token usage — verified offline against a Gemini-shaped stub stream.
- **SC-002**: A tool-using Gemini turn produces a raw `ToolCallRequest` (args passed through), and a context with a prior `ToolCallBlock`/`ToolResultBlock` builds `function_call`/`function_response` parts with the `skip_thought_signature_validator` sentinel — verified offline.
- **SC-003**: An `ImageBlock` maps to a Gemini `inline_data` part and the model advertises `accepts_media() == True` — verified offline.
- **SC-004**: A Gemini context-overflow signal raises `ContextOverflowError`; an error carrying a secret is normalized so the secret does not appear in the raised message — verified offline.
- **SC-005**: The core install (no `gemini` extra) still imports the package; offline tests pass with no SDK and no network.
- **SC-006**: The four quality gates stay green, including the unit-014 api-reference bijection (the new package's `__all__` is documented) — and the content model / event schema are demonstrably unchanged (no `content.py` / event-envelope edit, no `SCHEMA_VERSION` bump).
- **SC-007**: Adding a Gemini host to a `/v1/models` registry surfaces it in the existing UI selector with no frontend change.

## Assumptions

- **Native, not OpenAI-compatible**: Gemini's wire format differs from OpenAI chat-completions (`contents`/`parts`, `function_declarations`, `inline_data`, `usage_metadata`), so a real adapter + mapping is warranted rather than another `base_url` wrapper (the 035 follow-up).
- **Official SDK behind a lazy import**: the adapter targets the official `google-genai` package, imported lazily inside the client factory exactly as the unit-020 adapters do, so the package imports without the extra and is tested offline with a stub client.
- **Duck-typed stream mapping**: the Gemini chunk stream is consumed via `getattr`/`isinstance` (no SDK types in the mapping), so stand-in `SimpleNamespace` chunks drive a real decode offline — mirroring the unit-020 stub posture.
- **`thought_signature` — conservative**: Gemini 3 hard-requires the signature for multi-turn tool use, but Google's official `skip_thought_signature_validator` sentinel bypasses validation, so multi-turn works **without** a content-model change; preserving the *real* signature (for best cross-turn reasoning continuity) is the documented deferred VI/ADR follow-up.
- **Additive, reversible**: removing the `gemini` package, its test module, the `gemini` extra, and its api-reference section leaves units 020/035/036 untouched (Constitution X rollback). No runtime-core, gateway, event-bus, or content-model change to revert.
