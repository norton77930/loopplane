# Contracts: OpenAI-Compatible Providers (`loopplane.adapters.openai_compat`)

This unit exposes two constructors that return a unit-020 `OpenAIModel`. They
implement the existing `ModelBoundary` (via the reused `OpenAIModel`) and add no
new runtime contract.

## `openrouter_model(model, *, api_key=None, context_capacity=128000, max_output_tokens=None, client=None) -> OpenAIModel`

| Aspect | Contract |
|--------|----------|
| Returns | an `OpenAIModel` (so the OpenAI mapping + stream decoder + overflow/error handling apply unchanged) |
| Client | when `client is None`, built lazily with `base_url=OPENROUTER_BASE_URL` and `api_key` (the injected OpenRouter key) |
| Credential | injected by the caller/environment; never committed (VII) |
| `client` arg | bypasses the factory (offline tests) |

## `ollama_model(model, *, base_url=OLLAMA_BASE_URL, context_capacity=128000, max_output_tokens=None, client=None) -> OpenAIModel`

| Aspect | Contract |
|--------|----------|
| Returns | an `OpenAIModel` |
| Client | when `client is None`, built lazily with the given `base_url` (default local) and a placeholder key (`"ollama"`) |
| Credential | none required (Ollama ignores it) |
| `client` arg | bypasses the factory (offline tests) |

## Invariants

- Unit 020 (`OpenAIModel`, `OpenAIConfig`, `openai/mapping.py`) is **unchanged**.
- No new runtime dependency; `openai` is imported only inside the client factory.
- The package declares `__all__` and is documented in `docs/api-reference.md`
  (unit-014 bijection stays green).
- Registering an OpenRouter/Ollama host in the `/v1/models` registry surfaces it
  in the existing UI selector with no frontend change.
