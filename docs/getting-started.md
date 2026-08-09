# Getting started with LoopPlane

LoopPlane is an embeddable agent-harness runtime: you bring a model and a host
process; LoopPlane drives the conversation loop, governs every tool call through
one gateway, emits a normalized event stream, and (optionally) persists sessions.
This page gets you installed and running, then points to the deeper guides.

## Install

LoopPlane targets **Python 3.12+**. From a clone of the repository:

```sh
pip install .            # core: anyio + pydantic + jsonschema
pip install ".[web]"     # + the web/API host (FastAPI)
```

For development (the test toolchain — ruff, mypy, pytest), use uv:

```sh
uv sync
```

LoopPlane is not on a public package index yet, so the clone above is the
install path today; index install is the intended primary path and becomes
`pip install loopplane` with no other change once the first publish happens. The
full extras matrix (which extra for which deployment) is in the
[project README](../README.md#extras).

## Smallest end-to-end run

A deterministic scripted model ships with the runtime, so a full loop runs with
**no provider credentials and no network**. The smallest host-driven run is
`examples/host_quickstart.py`:

```sh
python examples/host_quickstart.py
```

To drive the loop-engineering entry point (`run_loop`) instead, see
`examples/loop_quickstart.py`. The full catalog is the
[examples index](../examples/README.md).

## Run the quality gates locally

The same gates CI runs:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

## Where to go next

- The runtime foundation, hands-on — [Embedding quickstart](./quickstart.md).
- Embedding via the host interface — [Host interface](./embedding-host.md).
- The full public surface — [API reference](./api-reference.md).
- Every guide — the [documentation index](./README.md).

The additive layers each have their own guide (loop engineering, scheduling,
validator/evaluator packs, human review, memory recall, the advanced tool
gateway, governance, observability, the web/API host, the studio host, and
multi-agent orchestration); all are linked from the documentation index.
