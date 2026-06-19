# Phase 1 Data Model: OpenAI-Compatible Model Providers

No new persisted entities. The unit adds two constructors and two constants in a
new public package; the underlying state is the reused `OpenAIModel`/`OpenAIConfig`.

## Reused (unchanged, unit 020)

- **`OpenAIModel`** — the model-boundary implementation over the OpenAI
  chat-completions API; built from an `OpenAIConfig`. Reused as-is.
- **`OpenAIConfig`** — carries `model`, `context_capacity`, `max_output_tokens`,
  `api_key`, `client`, and `client_factory: Callable[[str | None], Any]`. The
  **`client_factory` seam** is how this unit injects a `base_url` without
  changing 020.

## New public surface (`loopplane.adapters.openai_compat`)

| Name | Kind | Meaning |
|------|------|---------|
| `OPENROUTER_BASE_URL` | `str` constant | `https://openrouter.ai/api/v1` |
| `OLLAMA_BASE_URL` | `str` constant | `http://localhost:11434/v1` (default) |
| `openrouter_model(model, *, api_key=None, context_capacity=128000, max_output_tokens=None, client=None)` | constructor → `OpenAIModel` | OpenAI client pinned to OpenRouter + injected key |
| `ollama_model(model, *, base_url=OLLAMA_BASE_URL, context_capacity=128000, max_output_tokens=None, client=None)` | constructor → `OpenAIModel` | OpenAI client pinned to a local Ollama endpoint + placeholder key |

`__all__ = ["OLLAMA_BASE_URL", "OPENROUTER_BASE_URL", "ollama_model", "openrouter_model"]`
(documented 1:1 in `docs/api-reference.md` for the unit-014 bijection).

## Internal

- **`_base_url_client_factory(base_url) -> Callable[[str | None], Any]`** — a
  closure mirroring the OpenAI adapter's default client factory but pinning
  `base_url`; imports `openai` lazily.

## Validation / behavior rules

- FR-002/003: OpenRouter passes the injected key + OpenRouter base_url; Ollama
  passes a placeholder key + the (overridable) local base_url.
- FR-005: `client` (when provided) bypasses the factory → offline tests need no SDK.
- FR-004/008: the result is an `OpenAIModel` (boundary/mapping reused); the new
  package declares `__all__` and is documented (bijection).
