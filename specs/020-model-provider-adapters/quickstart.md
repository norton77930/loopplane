# Quickstart: Real Model-Provider Adapters

Drive the agent loop with a real model. Each adapter implements the existing model
boundary, so it slots into `RuntimeConfig(model=...)` with no other change. Install the
matching extra and inject your own API key — nothing is committed.

## Anthropic (Claude)

```
pip install ".[anthropic]"
export ANTHROPIC_API_KEY=...        # injected from the environment; never committed
```

```python
from loopplane.adapters.anthropic import AnthropicModel, AnthropicConfig
from loopplane.host import LoopPlaneHost, RuntimeConfig

model = AnthropicModel(AnthropicConfig(model="<a claude model name>"))
host = LoopPlaneHost(RuntimeConfig(model=model))
outcome = await host.run("Say hello.", on_event)
```

## OpenAI (GPT)

```
pip install ".[openai]"
export OPENAI_API_KEY=...
```

```python
from loopplane.adapters.openai import OpenAIModel, OpenAIConfig
from loopplane.host import LoopPlaneHost, RuntimeConfig

model = OpenAIModel(OpenAIConfig(model="<a gpt model name>"))
host = LoopPlaneHost(RuntimeConfig(model=model))
outcome = await host.run("Say hello.", on_event)
```

## Tools work unchanged

Register tools as usual (`RuntimeConfig(tools=...)`); the adapter advertises them to the
model and surfaces tool calls as `ToolCallRequest`, which the **gateway** validates and
executes. The model continues after each tool result — the standard loop round-trip.

## Testing without a key

The offline tests inject a **stub client** that yields stand-in provider events, so they
need no SDK network and no credential. The runnable examples
(`examples/anthropic_quickstart.py`, `examples/openai_quickstart.py`) print a clear
message and exit cleanly when no key is set. The one **live** test
(`tests/live/test_live_models.py`) is opt-in: it is skipped unless the provider key is
present and is excluded from the default CI gates.
