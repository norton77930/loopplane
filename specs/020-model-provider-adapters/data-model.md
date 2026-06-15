# Data Model: Real Model-Provider Adapters

No new runtime data types. The adapters reuse the existing model-boundary shapes
(`ModelRequest`, `Message`, `ContentBlock`, the `ModelIncrement` union, `TokenUsage`,
`ToolDescriptor`) and add only adapter classes and their configuration.

## Adapter classes

- **`AnthropicModel`** / **`OpenAIModel`** — each implements `ModelBoundary`:
  - `stream_turn(request: ModelRequest) -> AsyncIterator[ModelIncrement]` — an async
    generator that maps the provider stream to increments, ending a successful turn with
    exactly one `TurnEnd`.
  - `context_capacity() -> int` — the configured window size.
  - constructed from its config; holds no per-run state.

## Configuration

- **`AnthropicConfig`** / **`OpenAIConfig`** (frozen):
  - `model: str` — the provider model name (injected; no default model is assumed).
  - `context_capacity: int` — the assembler's budget (per-provider default, overridable).
  - `max_output_tokens: int | None` — default cap when `ModelRequest.limits` omits one.
  - `client: <async client> | None` — an **injected** client; when `None`, a default
    factory lazily imports the SDK and builds one from the injected credential/env.
  - `api_key: str | None` — an optional injected credential passed to the default
    factory; never stored in committed files, never logged.

## Increment mapping (provider stream → `ModelIncrement`)

| Normalized increment | Anthropic event | OpenAI chunk |
|---|---|---|
| `TextIncrement(text)` | `content_block_delta` → `text_delta.text` | `choices[0].delta.content` |
| `ReasoningIncrement(text)` | `content_block_delta` → `thinking_delta.thinking` | (none in chat-completions; omitted) |
| `ToolCallRequest(call_id, tool_name, input)` | a completed `tool_use` block (`id`,`name`, accumulated `input_json_delta` → parsed) | accumulated `delta.tool_calls[index]` (`id`,`function.name`, `function.arguments` → parsed) |
| `TurnEnd(stop_reason, usage)` | `message_delta`/`message_stop` (`stop_reason`, `usage`) | final chunk (`finish_reason`, trailing `usage`) |

Malformed tool-call JSON is surfaced as a `ToolCallRequest` with a best-effort `input`
(empty object on parse failure); the **gateway** validates it (Constitution V), the
adapter does not reject it.

## Request mapping (`ContentBlock` → provider message)

| `ContentBlock` | Anthropic | OpenAI |
|---|---|---|
| `TextBlock` | `{type: text, text}` | text content (string or `text` part) |
| `ImageBlock` | `{type: image, source: {type: base64, media_type: format, data: media}}` | `{type: image_url, image_url: {url: "data:<format>;base64,<media>"}}` |
| `ToolCallBlock` (assistant) | `{type: tool_use, id: call_id, name: tool_name, input}` | `{role: assistant, tool_calls: [{id: call_id, type: function, function: {name: tool_name, arguments: json(input)}}]}` |
| `ToolResultBlock` (user) | `{type: tool_result, tool_use_id: call_id, content: <outputs>, is_error: outcome=="failure"}` | `{role: tool, tool_call_id: call_id, content: <outputs/text>}` |
| `SummaryMarkerBlock` | a `text` block with a digest summary | a text message with a digest summary |

`ToolResultBlock.outputs` are `OutputBlock`s (text/image); text is joined for the tool
result content; a `failure` outcome maps to the provider's error flag where available.

## Tool descriptor mapping (`ToolDescriptor` → provider tool)

| Field | Anthropic | OpenAI |
|---|---|---|
| `name` | `name` | `function.name` |
| `description` | `description` | `function.description` |
| `input_schema` | `input_schema` | `function.parameters` |

## Usage mapping (provider usage → `TokenUsage`)

| `TokenUsage` field | Anthropic | OpenAI |
|---|---|---|
| `input_tokens` | `usage.input_tokens` | `usage.prompt_tokens` |
| `output_tokens` | `usage.output_tokens` | `usage.completion_tokens` |
| `cached_tokens` | `usage.cache_read_input_tokens` | `usage.prompt_tokens_details.cached_tokens` |
| `reasoning_tokens` | (0) | `usage.completion_tokens_details.reasoning_tokens` |

Absent fields default to 0.

## Errors

- `ContextOverflowError` (existing) — raised when the provider reports the prompt exceeds
  the model's window.
- A small adapter-internal exception (not exported in `__all__`) for other
  provider/transport faults, carrying a public-safe message (no credential, no raw body).
