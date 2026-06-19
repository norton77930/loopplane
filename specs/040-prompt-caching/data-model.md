# Phase 1 Data Model: Anthropic Prompt Caching

No new persisted entities, no event/content/usage-shape change. The unit adds one
config field and one pure overlay function in the Anthropic adapter package.

## Reused (unchanged)

- **`TokenUsage`** (`loopplane.model.boundary`) — already carries
  `cached_tokens`. Anthropic maps it from `cache_read_input_tokens`
  (`AnthropicStreamDecoder._apply_input_usage`); OpenAI from
  `prompt_tokens_details.cached_tokens` (`OpenAIStreamDecoder._apply_usage`).
  **Unchanged** — caching is observed through this existing field.
- **`build_messages(context)` / `build_tools(tools)`** (`anthropic/mapping.py`) —
  **unchanged, byte-identical**. The caching overlay is applied *after* these, by
  a separate function, so their output and the unit-020 tests are untouched.
- **`AnthropicStreamDecoder`** — unchanged.

## Modified

### `AnthropicConfig` (`anthropic/config.py`)

Add one additive field, alongside the existing `accepts_media` /
`max_output_tokens`:

| Field | Type | Default | Meaning |
|------|------|---------|---------|
| `prompt_caching` | `bool` | `True` | When `True`, the adapter attaches `cache_control: {"type": "ephemeral"}` to the stable prefix of the request (the last tool definition + the last content block of the first message when there are ≥2 messages). When `False`, the request is byte-identical to the pre-caching request. |

## New (internal — not exported)

### `apply_prompt_caching(messages, tools)` (`anthropic/mapping.py`)

A pure transform over the assembled request lists.

```text
apply_prompt_caching(
    messages: list[dict[str, Any]],   # build_messages(...) output
    tools: list[dict[str, Any]],      # build_tools(...) output (possibly empty)
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]
```

Behavior:

- **Tools**: if `tools` is non-empty, return a copy whose **last** tool dict
  carries `cache_control: {"type": "ephemeral"}` (the end of the stable tools
  segment). Empty `tools` → returned unchanged (still empty).
- **Messages**: if `len(messages) >= 2` and the **first** message has a non-empty
  `content` list, return a copy whose first message's **last content block**
  carries `cache_control: {"type": "ephemeral"}`. Otherwise return `messages`
  unchanged (single message → don't cache the rolling tail; empty content →
  nothing to mark).
- **Purity**: copies the dicts it marks (does not mutate the inputs in place), so
  any other holder of the un-marked output is unaffected. Marks at most **2**
  blocks (≤ the Anthropic 4-breakpoint maximum), only on **stable** boundaries.

## Validation / behavior rules

- FR-001/FR-002/FR-003: breakpoints on the stable prefix only (last tool + first
  message when ≥2 messages); never the rolling last message; ≤4 (here ≤2).
- FR-004/FR-006: with `prompt_caching=False` the adapter does not call the
  overlay → the request equals `build_messages` / `build_tools` output exactly.
- FR-007/FR-008: OpenAI sends no cache parameter; `cached_tokens` is mapped by the
  existing decoder; `TokenUsage` shape is unchanged.
- FR-010: no new public package or `__all__` name (`prompt_caching` is a field on
  the existing `AnthropicConfig`; `apply_prompt_caching` is a module-level
  function in `mapping.py`, which declares no `__all__`).
