# Quickstart: Anthropic Prompt Caching

Prompt caching is **on by default** for the Anthropic adapter. Repeated agent-loop
turns automatically re-read the stable request prefix (the tool definitions + the
leading first turn) from Anthropic's cache at ~0.1x input price instead of full
price — no code change required.

## Default (caching on)

```python
from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel

model = AnthropicModel(AnthropicConfig(model="claude-opus-4-8"))
# Every turn's request now carries cache_control on the last tool definition and
# on the first message's last content block (the stable prefix). Turn 1 writes the
# cache (~1.25x); turns 2+ read it (~0.1x).
```

## Turning caching off (byte-identical request)

```python
model = AnthropicModel(
    AnthropicConfig(model="claude-opus-4-8", prompt_caching=False)
)
# The assembled request is now byte-identical to the pre-caching behavior:
# no cache_control anywhere; same messages/tools shapes as before.
```

## Observing cache hits

Caching is visible through the **existing** usage — no new field:

```python
async for increment in model.stream_turn(request):
    if isinstance(increment, TurnEnd):
        print(increment.usage.cached_tokens)  # Anthropic cache_read_input_tokens
```

`TokenUsage.cached_tokens` is mapped from Anthropic's `cache_read_input_tokens`.
If it stays `0` across repeated identical-prefix turns, the prefix is likely below
the model's minimum cacheable size (~4096 tokens for Opus 4.x) — the breakpoint is
harmless, but nothing is cached until the prefix is large enough.

## OpenAI / OpenRouter / Ollama (automatic — nothing to configure)

OpenAI-family caching is **automatic, server-side**; the adapter sends no cache
parameter. The `cached_tokens` it reports already flows into
`TokenUsage.cached_tokens` via the existing stream decoder:

```python
from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

model = OpenAIModel(OpenAIConfig(model="gpt-4o"))
# Caching just happens; read increment.usage.cached_tokens the same way.
```

OpenRouter and Ollama (unit 035) reuse the OpenAI adapter unchanged, so they
inherit the same automatic caching.

## Live cache-savings check (opt-in)

The default test suite is fully offline. To watch a real cache hit, run the
opt-in, secret-gated Anthropic live check and inspect `cached_tokens` across two
identical-prefix turns — see `docs/real-model-validation.md` §5.
