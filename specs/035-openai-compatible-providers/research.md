# Phase 0 Research: OpenAI-Compatible Model Providers

## Decision 1 — Reuse OpenAIModel via the `client_factory` base_url seam

- **Decision**: OpenRouter and Ollama are thin constructors that build an
  `OpenAIModel` with a `client_factory` closure pinning the client's `base_url`
  (OpenRouter → `https://openrouter.ai/api/v1`; Ollama → `http://localhost:11434/v1`).
- **Rationale**: Both speak the OpenAI chat-completions wire format, so the
  unit-020 mapping + stream decoder + error/overflow handling are reused
  unchanged. The existing `OpenAIConfig.client_factory: Callable[[str | None], Any]`
  seam carries the base_url with **no change to unit 020** and **no new dependency**.
- **Alternatives considered**: A new full adapter per provider (rejected:
  duplicates the OpenAI mapping); adding `base_url` to `OpenAIConfig` +
  `default_client_factory` (rejected: changes a public 020 signature for no gain
  over a closure factory).

## Decision 2 — Native Gemini is deferred (this unit ships OpenAI-compatible only)

- **Decision**: Ship OpenRouter + Ollama now; defer a **native** Gemini adapter
  (direct Google GenAI API) to a follow-up.
- **Rationale**: A native Gemini adapter needs the Google GenAI SDK behind a new
  optional extra and careful `thought_signature` handling across multi-turn tool
  use — and preserving `thought_signature` may touch the shared content model
  (an ADR concern). OpenRouter already brokers Gemini (and 100+ models) behind the
  OpenAI wire format, so the user-facing "more providers" value is delivered now,
  reliably, with zero new dependency. (Decision taken with the maintainer.)
- **Alternatives considered**: Forcing a native Gemini adapter into this unit
  (rejected for now: larger, SDK-uncertain, and a possible content-model ADR —
  out of proportion to the immediate value given OpenRouter coverage).

## Decision 3 — Ollama placeholder key + overridable base_url

- **Decision**: Ollama's OpenAI-compatible endpoint ignores the API key, so the
  constructor passes a fixed placeholder (`"ollama"`) to satisfy the SDK client,
  and exposes an overridable `base_url` (default local daemon).
- **Rationale**: Local, credential-free models with a sensible default; remote
  Ollama hosts are supported by overriding `base_url`.

## Decision 4 — Offline test posture (fake `openai` module)

- **Decision**: Tests replace `sys.modules["openai"]` with a fake module whose
  `AsyncOpenAI` records its kwargs, asserting the correct `base_url`/key wiring;
  an injected-client test asserts both constructors return an `OpenAIModel`
  (reuse). No SDK, no network.
- **Rationale**: Deterministic, offline, and focused on what is NEW (the base_url
  wiring) — the OpenAI stream mapping itself is already covered by unit 020.
