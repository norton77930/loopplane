# Phase 0 Research: Native Google Gemini Model-Provider Adapter

This unit takes on the work spec 035 explicitly deferred (its research
Decision 2; ADR 0001 Follow-up #3). The findings below ground the design and, in
particular, settle the `thought_signature` question conservatively.

## Decision 1 — Native Gemini now ships (direct Google GenAI API), inverting 035 Decision 2

- **Decision**: Add a **native** Gemini adapter over the direct Google GenAI API
  (the official `google-genai` SDK) behind a new optional `gemini` extra — the
  inverse of 035 Decision 2, which shipped OpenRouter/Ollama and deferred this.
- **Rationale**: Gemini's wire format is **not** OpenAI chat-completions — it has
  its own `contents`/`parts` request shape, `function_declarations` tools,
  `inline_data` images, and `usage_metadata` accounting — so a thin `base_url`
  wrapper (the 035 pattern) cannot represent it; a real adapter + mapping is
  warranted. The direct API also exposes Gemini-specific signals (thinking parts;
  the per-`function_call` `thought_signature`) that the OpenAI-compatible broker
  flattens away. 035 deferred this for two stated reasons — "the Google GenAI SDK
  behind a new optional extra" and "careful `thought_signature` handling across
  multi-turn tool use … preserving `thought_signature` may touch the shared content
  model (an ADR concern)"; this unit resolves both (Decision 2 = the SDK/extra;
  Decision 3 = `thought_signature`).
- **Alternatives considered**: Stay OpenRouter-only (rejected — leaves the native
  Gemini signals and a first-class Gemini host unbuilt; 035 already named this the
  tracked follow-up). Re-implement a Gemini HTTP client by hand (rejected —
  re-derives what the official SDK provides; Constitution IX favors using the
  vendor SDK as a boundary adapter, like unit 020 uses `anthropic`/`openai`).

## Decision 2 — The official `google-genai` SDK, imported lazily (mirrors unit 020)

- **Decision**: Target the official **`google-genai`** package (import
  `from google import genai`; client `genai.Client(api_key=...)`), imported
  **lazily** inside the config's `default_client_factory`, exactly as the unit-020
  adapters import `anthropic`/`openai`. The async streaming call is
  `client.aio.models.generate_content_stream(model=..., contents=..., config=...)`;
  the request is configured via `from google.genai import types` —
  `types.GenerateContentConfig(tools=[types.Tool(function_declarations=[...])],
  max_output_tokens=...)`.
- **Rationale**: `google-genai` is the current official, actively maintained SDK
  (the older `google-generativeai` is legacy). Lazy import keeps the package
  importable **without** the `gemini` extra and keeps the SDK an optional
  dependency; an injected `client` (or `client_factory`) lets offline tests bypass
  the SDK entirely. The stream is consumed by **duck-typing** (`getattr`/
  `isinstance`) so the mapping needs no SDK types and stand-in `SimpleNamespace`
  chunks drive a real decode — the unit-020 posture verbatim.
- **Offline-resolution note**: if the `google-genai` wheel cannot be resolved in
  the offline gate environment, the import stays lazy + the extra declared and the
  offline **stub** tests carry the unit (exactly as unit 020 does for `anthropic`/
  `openai` when their SDKs are absent). An unresolvable optional dep must not block
  the gates.
- **Wire-shape facts (used by the mapping, all duck-typed)**:
  - Response/chunk parts: `chunk.candidates[0].content.parts`; each part may carry
    `.text`, `.function_call` (`.name` + `.args` dict), `.inline_data`
    (`.mime_type` + `.data`), `.thought` (a bool marking a thinking part), and
    `.thought_signature` (bytes).
  - Finish: `chunk.candidates[0].finish_reason` (e.g. `STOP`, `MAX_TOKENS`,
    `SAFETY`).
  - Usage: `chunk.usage_metadata` with `prompt_token_count`,
    `candidates_token_count`, `cached_content_token_count`, `thoughts_token_count`
    (the SDK exposes the camel-case JSON fields as snake_case attributes).
  - Request: `contents` is a list of `{"role": "user"|"model", "parts": [...]}`;
    a function result is a `user`-role part `{"function_response": {"name", "response"}}`;
    a tool is `{"function_declarations": [{"name", "description", "parameters"}]}`.
    The mapping emits **plain dicts** (the SDK accepts dict-shaped `contents`/
    `tools`), so it needs no SDK types and stays offline-testable.

## Decision 3 — `thought_signature`: CONSERVATIVE — the content model is UNCHANGED

- **Decision**: Do **not** add a field to the shared content model and do **not**
  bump `SCHEMA_VERSION`. Implement text / streaming / vision / usage / single-turn
  **and multi-turn** tool use correctly; make multi-turn function calling *work*
  against Gemini 3 by attaching Google's **official** sentinel
  `thought_signature = "skip_thought_signature_validator"` to a `function_call`
  part when re-mapping a prior `ToolCallBlock` (which carries no signature).
  Document that preserving the *real* per-call signature (for best cross-turn
  reasoning continuity) is a deferred VI/ADR follow-up.
- **What the research established**:
  - **Gemini 3** models *always* produce a `thought_signature` on a
    `function_call` and **hard-require** it echoed back: "The first functionCall
    part in each step of the current turn must include its thought_signature. If
    you omit a thought_signature for the first functionCall part in any step of the
    current turn, the request will fail with a 400 error." (Gemini **2.5** produces
    it optionally and does **not** require it; **text-only** generation is not
    blocked — omitting a signature there only "may degrade performance".)
  - **But Google provides an official escape hatch**: a function call sent back
    with a dummy `thought_signature` of `"context_engineering_is_the_way_to_go"` or
    `"skip_thought_signature_validator"` **skips validation**. (Google's own thought-
    signatures docs FAQ: "you can set the following dummy signatures … to skip
    validation.")
  - Therefore multi-turn tool use can be made **functional** against Gemini 3
    **without** a content-model change — the sentinel is the supported mechanism for
    exactly the "custom function-call blocks without a preserved signature" case.
- **Why conservative (not the content-model path)**: The brief's "ONLY IF" trigger
  requires **both** (a) Gemini hard-fails multi-turn tool use without a signature
  **and** (b) a clean additive carrier is the only way to make it work. (a) is true
  for Gemini 3, but **(b) is false** — the official skip sentinel makes it work
  without touching `ToolCallBlock`. Adding an optional `ToolCallBlock` field would
  change the **versioned event-schema contract** (Constitution VI), demand an
  ADR 0002 + serde round-trip/sizing tests + a `SCHEMA_VERSION` consideration, and
  enlarge the parent's content-model review surface — all to buy *reasoning-
  continuity quality* that the run does not *functionally* require. ADR 0001's whole
  philosophy (D1: "the content model and event schema are UNCHANGED … the parent's
  content-model review surface is therefore *empty*") is preserved by **not**
  changing the model. When unsure, the brief says choose the conservative path; here
  the conservative path is also strictly sufficient for function.
- **The documented limitation**: cross-turn reasoning continuity may degrade
  slightly versus a client that round-trips the genuine per-call signature, because
  the real signature has nowhere to live in the shared model. Recorded as the
  deferred follow-up: *if* a future unit wants real-signature preservation, it would
  add an optional, empty-defaulting, serde-round-tripped `ToolCallBlock` field under
  an ADR 0002 (Constitution VI), ignored by every other adapter.
- **Guardrails honored**: the sentinel goes on the Gemini `function_call` part's
  `thought_signature` field only — **never** smuggled into the tool-input `args`
  dict the gateway validates (Constitution V); no fake/random signature value is
  invented (only the documented sentinel is used).

## Decision 4 — Reuse the shared error normalization; map overflow → `ContextOverflowError`

- **Decision**: Reuse `adapters/_model_errors.py` (`ModelProviderError` +
  `error_text`). Normalize a Gemini context-overflow / resource-exhausted signal to
  `ContextOverflowError` (so the loop can compact + retry once); normalize every
  other provider/transport/credential failure to `ModelProviderError` with a
  public-safe message that leaks no key and no raw SDK/response body.
- **Rationale**: Consistency with the unit-020 adapters (same shared error type and
  loop behavior). Gemini signals an over-budget prompt via an HTTP 400 /
  `INVALID_ARGUMENT` whose message mentions the token/context limit, or an HTTP 429
  / `RESOURCE_EXHAUSTED`; the overflow probe matches those text/status signals
  defensively (duck-typed `getattr` on `status_code`/`code` + a lowercased message
  scan), mirroring the Anthropic/OpenAI `_is_overflow` helpers.
- **Alternatives considered**: a Gemini-specific error type (rejected — the loop
  only needs `ContextOverflowError` vs a generic provider error; the shared type
  keeps the loop's handling uniform).

## Decision 5 — Offline, deterministic test posture (mirrors unit 020)

- **Decision**: Default tests are offline with a Gemini-shaped **stub client** +
  stand-in `SimpleNamespace` chunks (text + `function_call` framing + `usage_metadata`
  + an overflow/error signal). The unit-test module covers the request mapping
  (`build_contents`/`build_tools`) and the `GeminiStreamDecoder` directly; the
  shared integration stub (`tests/integration/provider_stubs.py`) gains a Gemini
  entry so the existing parametrized overflow + failure + usage suites also exercise
  "gemini". Any live check is opt-in / secret-gated (`skipif` on the API-key + model
  env vars) and excluded from the gates (`docs/real-model-validation.md` extended
  with the Gemini env vars).
- **Rationale**: Deterministic, offline, no SDK and no network — the unit-020
  precedent verbatim. The duck-typed decoder makes a `SimpleNamespace` stream a
  faithful stand-in for the SDK's chunk objects.
