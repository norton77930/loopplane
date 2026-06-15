# Contract: Model-Provider Adapter

The behavioral contract every provider adapter (`AnthropicModel`, `OpenAIModel`) must
satisfy. It is verified by the unit mapping tests and the US1–US3 integration tests.

## Implements `ModelBoundary`

```
stream_turn(request: ModelRequest) -> AsyncIterator[ModelIncrement]
context_capacity() -> int
```

## `stream_turn` semantics

1. **Yields the normalized increment union only**: `TextIncrement`, `ReasoningIncrement`,
   `ToolCallRequest`, `TurnEnd`. No provider object escapes the adapter.
2. **Ends a successful turn with exactly one `TurnEnd`**, carrying the mapped
   `stop_reason` and `TokenUsage`. (The loop relies on `TurnEnd` to complete the turn.)
3. **Order is preserved**: text/reasoning increments are yielded in stream order; tool
   calls are yielded as their provider blocks complete.
4. **Tool calls are raw**: a `ToolCallRequest` carries the model's `call_id`, `tool_name`,
   and best-effort parsed `input`. The adapter never validates, authorizes, or executes —
   the gateway does (Constitution V).
5. **Context overflow → `ContextOverflowError`**: when the provider reports the prompt
   exceeds the model window, the adapter raises `ContextOverflowError` (the loop then
   compacts and retries exactly once).
6. **Other faults → a public-safe exception**: provider/transport errors raise a fresh
   exception whose message carries no credential and no raw response body/headers. The
   loop terminates the run as `unrecoverable-error` and emits no raw text.

## `context_capacity`

Returns the configured window size (a per-provider default, overridable). Pure; no I/O.

## Injected client

The adapter calls a narrow slice of an async client, consumed by duck-typing:

- **Anthropic**: an object exposing `messages.create(...)` (or `messages.stream(...)`)
  returning an async iterator of stream events with the attributes named in
  `data-model.md` (`type`, `delta`, `content_block`, `usage`, `message`, …).
- **OpenAI**: an object exposing `chat.completions.create(stream=True, ...)` returning an
  async iterator of chunks with `choices[0].delta` (`content`, `tool_calls`) and
  `choices[0].finish_reason`, plus a trailing chunk with `usage`.

The adapter accesses only documented public attributes and guards each with
`getattr`/`isinstance`, so a **stub client** that yields stand-in events satisfies the
contract with no SDK installed. The default client factory lazily imports the SDK and is
the only place the SDK name appears.

## Invariants

- Importing the adapter package succeeds **without** the SDK installed.
- The adapter holds no per-run mutable state shared across `stream_turn` calls.
- The credential is read only from the injected config/env and never appears in any
  yielded value, exception message, or log.
