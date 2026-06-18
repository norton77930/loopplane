# Model providers (unit 020)

LoopPlane drives the conversation loop through one model-facing seam — the **model
boundary**. A deterministic scripted model ships for tests and credential-free demos; this
unit adds two **real** model-provider adapters so you can run the loop against a live
model by bringing your own API key.

- `loopplane.adapters.anthropic` — `AnthropicModel` over the Anthropic messages API.
- `loopplane.adapters.openai` — `OpenAIModel` over the OpenAI chat-completions API.

Each adapter implements the existing boundary, so it slots into
`RuntimeConfig(model=...)` with no other change. Each wraps its **official SDK** behind its
own optional extra and imports that SDK lazily, so the adapter package imports even when
the extra is not installed.

## Install and run

The credential is read from the environment (or injected via the config); it is never
committed.

### Anthropic (Claude)

```
pip install ".[anthropic]"
export ANTHROPIC_API_KEY=...
```

```python
from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel
from loopplane.host import LoopPlaneHost, RuntimeConfig

model = AnthropicModel(AnthropicConfig(model="<a claude model name>"))
host = LoopPlaneHost(RuntimeConfig(model=model))
outcome = await host.run("Say hello.", on_event)
```

### OpenAI (GPT)

```
pip install ".[openai]"
export OPENAI_API_KEY=...
```

```python
from loopplane.adapters.openai import OpenAIConfig, OpenAIModel
from loopplane.host import LoopPlaneHost, RuntimeConfig

model = OpenAIModel(OpenAIConfig(model="<a gpt model name>"))
host = LoopPlaneHost(RuntimeConfig(model=model))
outcome = await host.run("Say hello.", on_event)
```

### OpenAI-compatible / self-hosted endpoints

The OpenAI adapter speaks the standard chat-completions API, so it drives **any
OpenAI-compatible endpoint** — a self-hosted server (vLLM, llama.cpp, LM Studio, …) or a
gateway, not only `api.openai.com`. Set it up in one of two ways.

The OpenAI SDK reads `OPENAI_BASE_URL` (and `OPENAI_API_KEY`) from the environment, so the
default adapter needs no code change:

```
export OPENAI_BASE_URL=https://your-host.example/v1   # the part before /chat/completions
export OPENAI_API_KEY=...
```

Or inject a client explicitly:

```python
from openai import AsyncOpenAI

from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

client = AsyncOpenAI(base_url="https://your-host.example/v1", api_key="...")
model = OpenAIModel(OpenAIConfig(model="<the served model name>", client=client))
```

`base_url` is everything before `/chat/completions`; it reuses the same
`OpenAIConfig.client` seam the offline tests use.

## Behavior

- **Streaming** — provider stream events are mapped to the loop's normalized increments
  (text, reasoning, tool-call, turn-end) in order.
- **Tools** — registered tools are advertised to the model; a tool call surfaces as a raw
  `ToolCallRequest` that the **gateway** validates and executes, and the model continues
  after the result (the standard loop round-trip).
- **Context overflow** — when the provider reports the prompt exceeds the model window,
  the adapter signals the loop to compact history and retry once.
- **Failures** — provider and transport errors surface as the loop's normalized failure;
  the credential and raw SDK internals never reach the caller or the event stream.
- **Usage** — token usage (input/output/cached/reasoning, where the provider reports it)
  is carried on the turn-completed event.

## Configuration

`AnthropicConfig` / `OpenAIConfig` carry the `model` name, the `context_capacity` the
assembler budgets against (a per-provider default, overridable), an optional
`max_output_tokens`, an optional injected `api_key`, and an optional injected `client`
(used by the offline tests in place of a real SDK client).

## Testing

The offline tests inject a stub client that yields stand-in provider events, so they need
no SDK network and no credential. The two runnable examples
(`examples/anthropic_quickstart.py`, `examples/openai_quickstart.py`) print a message and
exit cleanly when no key is set. A single opt-in, secret-gated live test
(`tests/live/test_live_models.py`) is skipped unless the provider key and a model name are
present, and is excluded from the default CI gates.
