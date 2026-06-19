# Quickstart: OpenAI-Compatible Providers

## Prerequisites

- Dev install (`pip install -e ".[dev]"`), Python 3.12+. The offline tests need
  no API key and no network.
- To actually call a provider: `pip install ".[openai]"`, plus an OpenRouter key
  (for OpenRouter) or a running local Ollama (for Ollama).

## Automated validation (primary, offline)

```powershell
uv run pytest tests/unit/test_openai_compat.py tests/contract/test_api_reference.py -q
```

**Expected**: green — the base_url/key wiring is asserted against a fake `openai`
module, the constructors return `OpenAIModel`, and the api-reference bijection
includes the new `loopplane.adapters.openai_compat` package.

Then the full gates:

```powershell
uv run ruff check .; uv run ruff format --check .; uv run mypy; uv run pytest -q
```

## Using a provider (illustrative)

```python
import os

from loopplane.adapters.openai_compat import openrouter_model, ollama_model

# OpenRouter (unlocks Claude, Gemini, Llama, … behind the OpenAI wire format).
# The key is injected from the environment, never committed (Constitution VII):
model = openrouter_model("google/gemini-2.0-flash", api_key=os.environ["OPENROUTER_KEY"])

# Local Ollama (no key):
model = ollama_model("llama3")  # or base_url="http://remote:11434/v1"
```

Register either as a model host in the `/v1/models` registry exactly as the
OpenAI host is registered (unit 028); the existing UI model selector lists it
with no frontend change.

## Rollback

Additive. Remove `src/loopplane/adapters/openai_compat/`, the `test_openai_compat.py`
module, and the `### loopplane.adapters.openai_compat` api-reference section;
units 020/028 are untouched (Constitution X).
