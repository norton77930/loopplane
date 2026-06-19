# Phase 1 Data Model: Native Google Gemini Model-Provider Adapter

**No new persisted entity, no new content block, and no event-schema change.** The
unit adds one new public package (a config + a model + an internal mapping) that
implements the **unchanged** `ModelBoundary` and reuses the existing conversation
content model and event schema as-is.

## Reused (unchanged)

- **`ModelBoundary`** (`loopplane.model.boundary`) — the model-provider interface
  (`stream_turn`, `context_capacity`); **unchanged** (still two methods).
  `GeminiModel` also exposes the additive duck-typed `accepts_media()` (unit 036).
- **The normalized increments** — `TextIncrement`, `ReasoningIncrement`,
  `ToolCallRequest`, `TurnEnd`, and `TokenUsage` — emitted by the decoder; reused
  as-is.
- **The content model** (`loopplane.model.content`) — `TextBlock`, `ImageBlock`,
  `ToolCallBlock`, `ToolResultBlock`, `SummaryMarkerBlock` — **UNCHANGED**.
  `ToolCallBlock` gains **no** signature field (the conservative `thought_signature`
  decision; research Decision 3).
- **The event schema** (`loopplane.events`) — **UNCHANGED**; **no `SCHEMA_VERSION`
  bump** (only normalized increments cross the loop seam, exactly as for the other
  adapters).
- **`ModelProviderError` + `error_text`** (`loopplane.adapters._model_errors`) —
  reused for public-safe error normalization.

## New public surface (`loopplane.adapters.gemini`)

| Name | Kind | Meaning |
|------|------|---------|
| `GeminiModel` | class (`ModelBoundary`) | a model boundary over the Google GenAI async streaming API |
| `GeminiConfig` | frozen dataclass | declarative config for `GeminiModel` |

`__all__ = ["GeminiConfig", "GeminiModel"]`
(documented 1:1 in `docs/api-reference.md` for the unit-014 bijection.)

### `GeminiConfig` fields

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `model` | `str` | — | the Gemini model id (e.g. `gemini-2.5-flash`) |
| `context_capacity` | `int` | `1_000_000` | the context window (Gemini windows are large) |
| `max_output_tokens` | `int \| None` | `None` | per-generation output cap (overridable per request) |
| `api_key` | `str \| None` | `None` | the injected Google API key (or `None` → SDK reads env) |
| `client` | `Any` | `None` | an injected ready client (tests/embedders) — bypasses the factory |
| `client_factory` | `Callable[[str \| None], Any]` | `default_client_factory` | builds the SDK client lazily from `api_key` |
| `accepts_media` | `bool` | `True` | whether the model accepts image input (036; ADR 0001 D5) |

## Internal (not public)

- **`default_client_factory(api_key) -> Any`** (`config.py`) — builds the official
  async Google GenAI client, importing `from google import genai` **lazily**;
  `genai.Client(api_key=api_key)` (or `genai.Client()` when `api_key is None`).
- **`build_contents(context) -> list[dict]`** (`mapping.py`) — maps the loop's
  `Message`/`ContentBlock` list to Gemini `contents`.
- **`build_tools(tools) -> list[dict]`** (`mapping.py`) — maps `ToolDescriptor`s to
  a Gemini `tools` list of `function_declarations` (empty list → no tools key).
- **`GeminiStreamDecoder`** (`mapping.py`) — stateful per-turn decoder turning the
  Gemini chunk stream into ordered normalized increments + one `TurnEnd`.
- **`SKIP_THOUGHT_SIGNATURE`** (`mapping.py`) — the literal
  `"skip_thought_signature_validator"` (Google's official multi-turn bypass), used
  only on a re-mapped `function_call` part's `thought_signature` (never in `args`).

## Request mapping (`ContentBlock`/`ToolDescriptor` → Gemini)

| Loop shape | Gemini wire (emitted as a plain dict) |
|------------|----------------------------------------|
| `Message(role="user")` | `{"role": "user", "parts": [...]}` |
| `Message(role="assistant")` | `{"role": "model", "parts": [...]}` |
| `TextBlock(text)` | `{"text": text}` |
| `ImageBlock(media, format)` | `{"inline_data": {"mime_type": format, "data": media}}` |
| `ToolCallBlock(call_id, tool_name, input)` | `{"function_call": {"name", "args"}, "thought_signature": SKIP_THOUGHT_SIGNATURE}` (role `model`) |
| `ToolResultBlock(call_id, outputs, error)` | `{"function_response": {"name", "response": {...}}}` (role `user`) |
| `SummaryMarkerBlock(digest)` | `{"text": <digest text>}` |
| `ToolDescriptor(name, description, input_schema)` | `{"function_declarations": [{"name", "description", "parameters": input_schema}]}` |

## Stream mapping (Gemini chunk → normalized increment)

| Gemini chunk element (duck-typed) | Normalized increment |
|-----------------------------------|----------------------|
| a part with `.text` and not `.thought` | `TextIncrement(text)` |
| a part with `.text` and `.thought is True` | `ReasoningIncrement(text)` |
| a part with `.function_call` (`.name`, `.args`) | accumulated → `ToolCallRequest(call_id, tool_name, input=args)` (raw) |
| `chunk.usage_metadata.prompt_token_count` | `TokenUsage.input_tokens` |
| `…candidates_token_count` | `TokenUsage.output_tokens` |
| `…cached_content_token_count` | `TokenUsage.cached_tokens` |
| `…thoughts_token_count` | `TokenUsage.reasoning_tokens` |
| `chunk.candidates[0].finish_reason` | `TurnEnd.stop_reason` (stringified) |
| end of stream | exactly one `TurnEnd(stop_reason, usage)` |

A `function_call` carries no provider call id, so the decoder synthesizes a stable
`call_<n>` id (mirroring the OpenAI decoder's `call_{index}` fallback); the args
dict is passed through **raw** for the gateway to validate.

## Validation / behavior rules

- FR-003/004: text/reasoning parts yield increments immediately; `function_call`
  parts accumulate and emit raw `ToolCallRequest`s, then one `TurnEnd` at finish.
- FR-005: each `ContentBlock` maps per the request table; a `ToolResultBlock`
  becomes a `user`-role `function_response`.
- FR-006: a context-overflow signal → `ContextOverflowError`; any other failure →
  `ModelProviderError` (public-safe; no key/raw-body leak).
- FR-007: `accepts_media()` returns the config flag (default `True`); the
  `ModelBoundary` Protocol is unchanged.
- FR-008: re-mapping a prior `ToolCallBlock` attaches `SKIP_THOUGHT_SIGNATURE` on
  the `function_call` part — **not** in `args`; no content-model field, no
  `SCHEMA_VERSION` bump.
- FR-010: the package declares `__all__` and is documented 1:1 (the 014 bijection).
