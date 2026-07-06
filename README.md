# LoopPlane

**Spec-first, embeddable agent harness runtime.**

LoopPlane is a Python-first foundation for building observable, governed,
tool-using AI agents. You bring a model and a host process; LoopPlane drives the
conversation loop, governs every tool call through one gateway, emits a single
normalized event stream, and (optionally) persists sessions so they survive a
crash.

## Install

LoopPlane targets **Python 3.12+**. From a clone of the repository:

```sh
pip install .            # core: anyio + pydantic + jsonschema
pip install ".[web]"     # + the web/API host (FastAPI)
```

Optional extras cover the model providers (`anthropic`, `openai`, `gemini`),
MCP, networking, OAuth, OpenTelemetry, and Postgres — see
[Getting started](docs/getting-started.md) for the full list. Installing the
package also provides the `loopplane` console script (the CLI host).

For development, `uv sync` installs the test toolchain (ruff, mypy, pytest).
Publishing to a public package index is a future step.

## Quickstart

See **[Getting started](docs/getting-started.md)**. A deterministic scripted model
ships with the runtime, so the smallest run needs no credentials:

```sh
python examples/host_quickstart.py
```

## What you get

- **Governed runtime core** — the agent loop, one Tool Gateway (internal + MCP
  tools), one normalized event stream, and durable checkpoint / resume with
  file, SQLite, and Postgres backends. See [capabilities](docs/capabilities.md).
- **Agent tools** — file editing and search, shell execution (optionally
  sandboxed), web fetch / search, notebooks, todo lists, subagents, background
  tasks and scheduling, and MCP tools + resources over
  stdio / HTTP / SSE / WebSocket. See [capabilities](docs/capabilities.md).
- **Model providers** — Anthropic, OpenAI(-compatible), Google Gemini,
  OpenRouter, and Ollama, each behind its own extra; structured output and
  image + document input where the provider supports it.
  See [model providers](docs/model-providers.md).
- **Governance & loop engineering** — permission rules and named permission
  modes, plan mode, human review, validators / evaluators with retry / repair,
  and hooks / plugins. See [loop engineering](docs/loop-engineering.md) and
  [governance](docs/sandbox-policy-governance.md).
- **Cost & budget** — pricing, USD budget caps (per message, session, and user
  month), a pre-turn cost guard, and queryable spend.
  See [capabilities](docs/capabilities.md).
- **Multi-tenant platform** — principal auth with an optional OAuth / JWT
  verifier, per-principal host pools, per-tenant fairness quotas, and durable
  SSE / WebSocket reconnect replay. See [web/API host](docs/web-api-host.md).
- **Hosts** — an embedding API, a CLI with slash commands, the web/API host, a
  web SPA, and a desktop studio host.
  See [embedding host](docs/embedding-host.md), [CLI](docs/cli.md), and
  [web frontend](docs/web-frontend.md).

## Documentation

- [Getting started](docs/getting-started.md) — install and first run.
- [Capabilities](docs/capabilities.md) — the full functional scope.
- [API reference](docs/api-reference.md) — every public package and name.
- [Documentation index](docs/README.md) — all guides.
- [Examples](examples/README.md) — runnable, credential-free quickstarts.

## Development

The project standardizes on [uv](https://github.com/astral-sh/uv). The quality
gates (also run in CI) are:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

## Design principles

LoopPlane is built spec-first: every change traces to a spec, plan, and task list
under `specs/`, with boundary decisions recorded as ADRs. The runtime is a clean,
fully owned architecture (no agent framework as the core), with strict component
boundaries — one tool gateway, one normalized event bus. Features land additive
and default-off, and every committed file is public-safe.

## License

LoopPlane is released under the [MIT License](LICENSE).
