# Contract: Native Gemini Model-Provider Adapter

The behavioral contract `GeminiModel` must satisfy. It is the same `ModelBoundary`
contract the unit-020 adapters satisfy, applied to Gemini's wire format. Verified
by the unit mapping tests (`tests/unit/test_gemini_mapping.py`) and the shared,
parametrized integration suites (`tests/integration/test_us2_model_overflow.py`,
`...test_us3_model_failures.py`) once `"gemini"` is added to the provider stub.

## Implements `ModelBoundary`

```
stream_turn(request: ModelRequest) -> AsyncIterator[ModelIncrement]
context_capacity() -> int
accepts_media() -> bool   # additive (unit 036; ADR 0001 D5); not part of the Protocol
```

The `ModelBoundary` Protocol is **unchanged** (still `stream_turn` +
`context_capacity`); `accepts_media()` is the additive duck-typed signal.

## `stream_turn` semantics

1. **Yields the normalized increment union only**: `TextIncrement`,
   `ReasoningIncrement`, `ToolCallRequest`, `TurnEnd`. No Gemini/SDK object escapes
   the adapter.
2. **Ends a successful turn with exactly one `TurnEnd`**, carrying the mapped
   `stop_reason` (from `finish_reason`) and `TokenUsage` (from `usage_metadata`).
3. **Order is preserved**: text/reasoning increments are yielded in stream order;
   tool calls are yielded as their `function_call` parts complete (a single turn's
   `function_call`s emitted before the `TurnEnd`).
4. **Tool calls are raw**: a `ToolCallRequest` carries a synthesized stable
   `call_id`, the `tool_name`, and the args dict **passed through unmodified**. The
   adapter never validates, authorizes, or executes — the gateway does
   (Constitution V).
5. **Reasoning is best-effort**: a thought/thinking part (`part.thought is True`)
   maps to a `ReasoningIncrement`; when the model emits none, no reasoning
   increment is produced (graceful degradation).
6. **Context overflow → `ContextOverflowError`**: when Gemini reports the prompt
   exceeds the model window (a 400/`INVALID_ARGUMENT` naming the token/context
   limit, or a 429/`RESOURCE_EXHAUSTED`), the adapter raises `ContextOverflowError`
   (the loop then compacts and retries exactly once).
7. **Other faults → a public-safe exception**: provider/transport/credential errors
   raise `ModelProviderError` whose message carries **no credential and no raw
   response body/headers**. The loop terminates the run as `unrecoverable-error`
   and emits no raw text.

## Multi-turn tool use (`thought_signature`)

- When `build_contents` re-maps a prior `ToolCallBlock`, it attaches Google's
  official sentinel `thought_signature = "skip_thought_signature_validator"` to the
  emitted `function_call` part, so Gemini 3 does **not** 400 on a missing signature.
- The sentinel goes on the part's `thought_signature` field **only** — never into
  the tool-input `args` dict the gateway validates (Constitution V). No fake or
  random signature value is invented.
- The **content model is unchanged** (`ToolCallBlock` has no signature field; no
  `SCHEMA_VERSION` bump). Preserving the *real* per-call signature is a documented
  deferred follow-up (a Constitution VI / ADR matter).

## `context_capacity`

Returns the configured window size (default `1_000_000`; Gemini windows are large,
overridable per model). Pure; no I/O.

## `accepts_media`

Returns the configured flag (default `True` — Gemini is vision-capable;
overridable). An `ImageBlock` in the request maps to a Gemini `inline_data` part.

## Injected client

The adapter calls a narrow slice of an async client, consumed by **duck-typing**:
an object exposing `aio.models.generate_content_stream(...)` returning an async
iterator of chunks with `candidates[0].content.parts` (each part guarded for
`.text` / `.thought` / `.function_call` / `.inline_data`),
`candidates[0].finish_reason`, and `usage_metadata` (`prompt_token_count`,
`candidates_token_count`, `cached_content_token_count`, `thoughts_token_count`).

The adapter accesses only documented public attributes and guards each with
`getattr`/`isinstance`, so a **stub client** that yields stand-in events satisfies
the contract with **no SDK installed**. The default client factory lazily imports
`from google import genai` and is the only place the SDK name appears.

## Invariants

- Importing `loopplane.adapters.gemini` succeeds **without** the `google-genai` SDK
  installed.
- The adapter holds no per-run mutable state shared across `stream_turn` calls (the
  decoder is constructed per turn).
- The credential is read only from the injected config/env and never appears in any
  yielded value, exception message, or log.
