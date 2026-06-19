# Contract: Anthropic Prompt Caching Overlay

This contract pins the observable behavior of the prompt-caching overlay and the
config toggle. It is enforced by `tests/unit/test_anthropic_caching.py` (and the
OpenAI confirmation in `tests/unit/test_openai_mapping.py`).

## C1 — Caching ON: tools breakpoint

When `prompt_caching=True` and `tools` is non-empty, the assembled `tools` block's
**last** element carries `cache_control: {"type": "ephemeral"}`; no earlier tool
carries it. Each tool otherwise keeps its `name` / `description` / `input_schema`
exactly as `build_tools` produced.

## C2 — Caching ON: messages stable-prefix breakpoint

When `prompt_caching=True` and the context has **two or more** messages, the
**first** message's **last content block** carries `cache_control: {"type":
"ephemeral"}`. The **last** message (the rolling tail) carries no `cache_control`
on any of its blocks.

## C3 — Caching ON: never exceed 4 breakpoints; never the tail

In any assembled request, the count of `cache_control` markers is **≤ 4** (this
implementation emits at most 2: the last tool + the first message). No marker
appears on the last message's content blocks.

## C4 — Caching ON: degenerate inputs

- No tools → no tools marker (the empty list is unchanged); the messages-prefix
  marker still applies when there are ≥2 messages.
- Single message → **no** messages marker (it would be the rolling tail); only
  the tools marker (if any) is added.
- First message with empty `content` → no messages marker (nothing to mark).

## C5 — Caching OFF: byte-identical request

When `prompt_caching=False`, the assembled `messages` equal `build_messages(...)`
exactly and the assembled `tools` equal `build_tools(...)` exactly — no
`cache_control` key appears anywhere. The streamed increments and `TokenUsage`
are unchanged from the pre-caching behavior.

## C6 — OpenAI: automatic, already reported, no request change

The OpenAI adapter sends **no** cache-control parameter. A usage chunk carrying
`prompt_tokens_details.cached_tokens = N` results in `TurnEnd.usage.cached_tokens
== N`. (OpenRouter/Ollama inherit this via the reused `OpenAIModel` + mapping.)

## C7 — Purity / non-mutation

`apply_prompt_caching` does not mutate its inputs in place; it returns new lists
with copies of the marked dicts, so a caller holding the original `build_messages`
/ `build_tools` output sees no `cache_control`.

## C8 — No boundary / schema change

No event-schema, content-model, or `TokenUsage`-shape change; no change to the
loop, runtime core, Tool Gateway, or Event Bus; no new public package or
`__all__` name.
