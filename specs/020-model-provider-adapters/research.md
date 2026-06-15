# Research: Real Model-Provider Adapters

Phase 0 decisions for unit 020. Each decision records the choice, the rationale, and
the alternatives rejected.

## D1 — The model boundary is the integration seam (not the gateway)

**Decision**: Implement the existing `ModelBoundary` protocol (`stream_turn`,
`context_capacity`) and nothing else. The adapter's `stream_turn` is an async generator
that yields the normalized increment union and ends a successful turn with **exactly one
`TurnEnd`**.

**Rationale**: `AgentLoop._stream_model_turn` iterates `stream_turn` and relies on a
`TurnEnd` to mark the turn complete; the surrounding `run` loop catches
`ContextOverflowError` (compact history and retry exactly once) and **any other
`Exception`** (terminate the run as `unrecoverable-error`). Crucially, the loop emits the
raw exception **nowhere** — `run_terminated` carries only a reason code. So the model
side's error contract differs from the gateway's: the adapter does **not** build a
`NormalizedError` (that is the gateway's tool-error model); it raises
`ContextOverflowError` for capacity and a fresh, public-safe exception otherwise.

**Rejected**: routing model errors through the gateway's `NormalizedError` — wrong
boundary; the gateway owns *tool* errors, not model errors.

## D2 — Duck-typed event mapping

**Decision**: The stream-mapping consumes provider event objects by attribute
(`getattr` + `isinstance` narrowing), not by importing the SDK's event type unions.

**Rationale**: It mirrors the existing MCP adapter (`getattr(item, "text", None)` then
`isinstance(...)`), decouples the mapping from SDK type-name churn, keeps `mypy --strict`
green (narrowing `Any`/`object` to `str`/`int`/`list` before constructing typed
increments avoids `warn_return_any`), and makes the offline tests trivial: a test injects
plain stand-in events (small objects with the right attributes) with no SDK installed.

**Rejected**: importing each SDK's streaming-event union and matching on concrete types —
brittle across SDK versions and forces the SDK into the offline tests.

## D3 — Injectable, lazily-built client

**Decision**: Each adapter's config carries an **injectable async client** (or a factory
that builds one). The default factory **lazily imports** the SDK and constructs the
provider's async client from injected credentials/environment. Tests pass a stub client.

**Rationale**: Module import must succeed without the SDK (the packaging contract imports
every public subpackage), so the `from anthropic import ...` / `from openai import ...`
lives **inside** the factory, never at module top — exactly the MCP adapter's pattern.
Injection keeps credentials and network out of the offline tests.

**Rejected**: constructing the SDK client in the adapter constructor / at import time —
would break import-without-SDK and force credentials into tests.

## D4 — Per-provider streaming shape (the mapping source of truth)

**Anthropic** (`client.messages.stream(...)` / streaming `create`): events
`message_start` (carries `usage.input_tokens`), `content_block_start`
(`text` | `tool_use` with `id`,`name`), `content_block_delta`
(`text_delta.text` | `input_json_delta.partial_json` | `thinking_delta.thinking`),
`content_block_stop`, `message_delta` (`delta.stop_reason`; `usage.output_tokens`),
`message_stop`. Tool input arrives as `partial_json` fragments per content-block index
and is JSON-parsed at the block stop. Mapping: `text_delta` → `TextIncrement`;
`thinking_delta` → `ReasoningIncrement`; a completed `tool_use` block → `ToolCallRequest`;
`message_delta`/`message_stop` → `TurnEnd(stop_reason, usage)`.

**OpenAI** (`client.chat.completions.create(stream=True, stream_options={"include_usage": True})`):
each `ChatCompletionChunk` has `choices[0].delta` with `content` (text) and `tool_calls`
(deltas with `index`, `id`, `function.name`, `function.arguments` fragments) and
`choices[0].finish_reason` (`stop` | `tool_calls` | `length`); a trailing chunk carries
`.usage`. Tool calls accumulate by `index` and are assembled (arguments concatenated, then
JSON-parsed) at the end. Mapping: `delta.content` → `TextIncrement`; assembled tool calls
→ `ToolCallRequest`; the final state → `TurnEnd(stop_reason=finish_reason, usage)`. OpenAI
does not stream reasoning text in the chat-completions surface, so no `ReasoningIncrement`
is emitted unless a reasoning delta is present.

## D5 — Request building (`ModelRequest` → provider request)

The loop hands `ModelRequest(context: list[Message], tools: list[ToolDescriptor], limits)`.
Each `Message` has a role and `ContentBlock`s. Mapping per provider:

- **Anthropic** messages (block content): `TextBlock` → `{type: text}`; `ImageBlock` →
  `{type: image, source: {type: base64, media_type, data}}`; `ToolCallBlock` (assistant) →
  `{type: tool_use, id, name, input}`; `ToolResultBlock` (user) →
  `{type: tool_result, tool_use_id, content, is_error}`; `SummaryMarkerBlock` → a `text`
  block carrying the digest summary. Tools → `{name, description, input_schema}`.
  `limits.max_output_tokens` → `max_tokens` (with a sane default when absent).
- **OpenAI** messages (role-shaped): assistant `TextBlock` → `{role: assistant, content}`;
  `ToolCallBlock` → `{role: assistant, tool_calls: [{id, type: function, function: {name,
  arguments}}]}`; `ToolResultBlock` → `{role: tool, tool_call_id, content}`; `ImageBlock`
  → an `image_url` content part with a `data:` URL; `SummaryMarkerBlock` → a system/user
  text part. Tools → `{type: function, function: {name, description, parameters}}`.

## D6 — Usage mapping (`→ TokenUsage`)

`TokenUsage(input_tokens, output_tokens, cached_tokens, reasoning_tokens)`. Anthropic:
`usage.input_tokens` → input, `usage.output_tokens` → output,
`usage.cache_read_input_tokens` → cached. OpenAI: `usage.prompt_tokens` → input,
`usage.completion_tokens` → output, `prompt_tokens_details.cached_tokens` → cached,
`completion_tokens_details.reasoning_tokens` → reasoning. Missing fields default to 0.

## D7 — Context capacity is configured, not probed

**Decision**: `context_capacity()` returns a value from the adapter's config (a sensible
default per provider, overridable). **Rationale**: providers do not expose the window
reliably at runtime; the assembler only needs a budget number. **Rejected**: hardcoding or
probing the API.

## D8 — Optional extras, lazy import, contract obligations

Each SDK is its own optional extra (`anthropic`, `openai`); the dev group adds both so
`mypy --strict` and tests can type-check the adapters. The packaging contract test pins
the extras set, so it is updated to `{anthropic, mcp, openai, otel, web}` (the runtime
dependency set is unchanged). Each new public package (`__all__`) is documented in
`docs/api-reference.md` (the api-reference drift contract compares documented names to
`__all__`), and is importable without its SDK (the packaging import contract).

## D9 — Error safety

Provider/transport exceptions are caught and re-raised as a fresh, public-safe exception
whose message contains no credential and no raw response body/headers — only a short,
safe summary. Overflow is detected by inspecting the provider's "context too long" error
(HTTP 400 with the provider's length code/message) and raised as `ContextOverflowError`
so the loop compacts and retries. The loop keeps any model exception off the event
stream regardless (D1), so this is defense in depth plus testable clarity.

## D10 — Testing split

- **Unit** (`tests/unit/test_*_mapping.py`): pure mapping — `ModelRequest` → provider
  request, and stand-in provider events → increments — no loop, no SDK.
- **Integration** (`tests/integration/test_us1-3_*`): a stub client drives `AgentLoop`
  end-to-end (text, tool-use round-trip, overflow→compact-retry, public-safe failure +
  usage), parametrized over both adapters.
- **Live** (`tests/live/test_live_models.py`): opt-in, `skipif` on the absence of the
  provider API-key env var; **excluded from CI** (CI references no secret). Carries the
  foundation unit's reserved real-model validation.
- **Examples**: `examples/*_quickstart.py` lazily import the SDK and exit cleanly with a
  message when no key is set, so they never fail a no-credential run.
