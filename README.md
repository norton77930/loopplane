# LoopPlane

[![CI](https://github.com/norton77930/loopplane/actions/workflows/ci.yml/badge.svg)](https://github.com/norton77930/loopplane/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

**Spec-first, embeddable agent harness runtime.**

LoopPlane is a Python-first foundation for building observable, governed,
tool-using AI agents. You bring a model and a host process; LoopPlane drives the
conversation loop, governs every tool call through one gateway, emits a single
normalized event stream, and (optionally) persists sessions so they survive a
crash.

## Install

LoopPlane targets **Python 3.12+**.

> **Publication status:** LoopPlane is not on a public package index yet, so the
> install below is from a clone. Index install is the intended primary path and
> the release machinery is in place; this note goes away with the first publish.

```sh
git clone https://github.com/norton77930/loopplane.git
cd loopplane
pip install .            # core: anyio + pydantic + jsonschema
pip install ".[web]"     # + the web/API host (FastAPI)
```

After the first publish the same two lines become `pip install loopplane` and
`pip install "loopplane[web]"`, with no other change. Installing the package
provides the `loopplane` console script (the CLI host).

For development, `uv sync` installs the test toolchain (ruff, mypy, pytest); see
[Contributing](CONTRIBUTING.md).

### Extras

The base install is deliberately small — anyio, pydantic, jsonschema. Everything
else is an optional extra:

| Extra | Pulls in | Install it for |
| --- | --- | --- |
| `anthropic` | Anthropic SDK | Claude models |
| `openai` | OpenAI SDK | OpenAI, OpenRouter, Ollama, and any OpenAI-compatible endpoint |
| `gemini` | Google GenAI SDK | native Gemini models |
| `web` | FastAPI | the Python web/API host (REST + SSE + WebSocket); the SPA is built separately under `apps/web` |
| `mcp` | MCP SDK | MCP servers and MCP resources |
| `net` | httpx | `web_fetch` / `web_search` (still default-deny until enabled) |
| `oauth` | PyJWT + httpx | OAuth / JWT / JWKS principal verification |
| `postgres` | psycopg | Postgres checkpoint, ledger, and event-replay backends |
| `otel` | OpenTelemetry API | OpenTelemetry observability export |
| `all` | every extra above | trying LoopPlane out, or a deployment that genuinely wants the lot |

`all` is a convenience alias, not a recommendation — it pulls in every SDK above, including
psycopg and three model vendors. Prefer naming what you need. Combine extras freely, for example:

```sh
pip install ".[anthropic]"                        # local CLI against Claude
pip install ".[web,openai]"                       # single-node web service
pip install ".[web,anthropic,postgres,oauth]"     # multi-tenant deployment
pip install ".[web,anthropic,mcp,net,postgres,oauth,otel]"   # everything server-side
```

There is no `all` convenience extra yet — adding one is a maintainer decision
(see [Governance](GOVERNANCE.md)).

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
- [Documentation index](docs/README.md) — all guides, including the thematic
  capability guides under `docs/guides/`.
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

## Contributing

Issues and pull requests are welcome. Start with
[CONTRIBUTING.md](CONTRIBUTING.md) — especially its **hazard map**, which lists
the deliberately kept compromises (two quarantined import boundaries, the
boundary-guard tests, the default-off rule) that should not be "fixed".
[GOVERNANCE.md](GOVERNANCE.md) explains who decides what and which changes need
a maintainer decision before implementation. Security reports go through
[SECURITY.md](SECURITY.md), never a public issue.

## Design principles

LoopPlane is built spec-first: every change traces to a spec, plan, and task list
under `specs/`, with boundary decisions recorded as ADRs. The runtime is a clean,
fully owned architecture (no agent framework as the core), with strict component
boundaries — one tool gateway, one normalized event bus. Features land additive
and default-off, and every committed file is public-safe.

## License

LoopPlane is released under the [MIT License](LICENSE).
