# LoopPlane

**Spec-first, embeddable control plane for loop-engineered AI agents.**

LoopPlane is a Python-first foundation for building observable, governed,
tool-using AI agents. You bring a model and a host process; LoopPlane drives the
conversation loop, governs every tool call through one gateway, emits a single
normalized event stream, and (optionally) persists sessions so they survive a
crash — with additive layers for loop engineering, scheduling, validation, human
review, recall, governance, observability, web/desktop hosting, and multi-agent
orchestration on top.

## Install

LoopPlane targets **Python 3.12+**. From a clone of the repository:

```sh
pip install .            # core: anyio + pydantic + jsonschema
pip install ".[web]"     # + the web/API host (FastAPI)
```

For development, `uv sync` installs the test toolchain (ruff, mypy, pytest).
Publishing to a public package index is a future step.

## Quickstart

See **[Getting started](docs/getting-started.md)**. A deterministic scripted model
ships with the runtime, so the smallest run needs no credentials:

```sh
python examples/host_quickstart.py
```

## Layer map

| Unit | Package | What it adds |
|---|---|---|
| 001 | `loopplane` runtime (`loop`, `controller`, `gateway`, `events`, …) | The agent-harness runtime: agent loop, tool gateway, normalized events, memory, checkpointing, artifacts, approval. |
| 002 | `loopplane.host` | The Host Application Interface — embed the runtime from one config object. |
| 003 | `loopplane.engineering` | Loop engineering: loop definitions, triggers, validators, evaluators, retry/repair, loop events. |
| 004 | `loopplane.scheduling` | The local scheduler and trigger engine. |
| 005 | `loopplane.packs` | Reusable validators and evaluators. |
| 006 | `loopplane.review` | Human-review workflows. |
| 007 | `loopplane.recall` | Memory recall and knowledge indexing. |
| 008 | `loopplane.toolkit` | Advanced tool gateway: discovery, registry, manifests, versioning. |
| 009 | `loopplane.governance` | Sandbox, policy, and cost governance. |
| 010 | `loopplane.inspect` | Read-only observability: trace, timeline, diagnostics. |
| 011 | `loopplane.webapi` | The web/API host transport. |
| 012 | `loopplane.studio` | The local desktop/studio host. |
| 013 | `loopplane.orchestration` | Multi-agent orchestration: subagents, coordinator, delegation. |

## Documentation

- [Getting started](docs/getting-started.md) — install and first run.
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
under `specs/`. The runtime is a clean, fully owned architecture (no agent
framework as the core), with strict component boundaries — one tool gateway, one
normalized event bus — and every committed file is public-safe.

## License

LoopPlane is released under the [MIT License](LICENSE).
