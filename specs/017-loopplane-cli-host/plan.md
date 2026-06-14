# Implementation Plan: LoopPlane CLI Host

**Branch**: `017-loopplane-cli-host` (main-only) | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/017-loopplane-cli-host/spec.md`

## Summary

Add a thin terminal host (`loopplane.cli`) and a console entry point `loopplane`
over the public Host Application Interface (`loopplane.host`). The CLI runs prompts
through `LoopPlaneHost.run`, renders the run from the **normalized event stream**,
and offers `chat` (interactive), `run` (one-shot), and `sessions` (list/resume when
a durable store is configured). It is **credential-free by default** (a built-in
scripted demo model, no network) and selects a real model only when the
environment points at an importable `ModelBoundary` builder — the concrete network
provider is out of scope (bring-your-own behind the seam, validated manually like
unit 001). The CLI executes no tool and re-emits no bus (V/VI); it is additive — the
entry point and package change no runtime behavior, and installing without invoking
the CLI changes nothing (FR-010/SC-005).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: standard library (`argparse`) + `anyio` (already core) — no
new dependency for the core CLI; a real provider lives behind an optional extra

**Storage**: N/A (durable sessions reuse the host's configured checkpoint store)

**Testing**: pytest — the command dispatch, one-shot run, renderer, and provider
selection are exercised with a scripted model + captured streams (no real interactivity)

**Project Type**: single library + a console entry point

**Performance Goals**: interactive latency bound by the model; the CLI adds negligible overhead

**Constraints**: thin host — composes only `loopplane.host`; public-safe output; no
new core dependency; additive entry point

**Scale/Scope**: one new subpackage (~4 modules) + a `[project.scripts]` entry + docs/example

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md`. | PASS |
| II — Greenfield | Fresh code; no legacy/`openspec` copy (the CLI is written from the spec, not from any reference CLI). | PASS |
| III — Harness before automation | A host surface; adds no automation engine. | PASS |
| IV — Boundary Clarity | One responsibility (a terminal host); interacts only through the public `loopplane.host` interface. | PASS |
| V — Tool Gateway Ownership | The CLI executes no tool; tools run through the runtime gateway, the CLI only renders events. | PASS (FR-008) |
| VI — Event Bus Ownership | The CLI is a host *consumer* of the normalized event stream; it re-emits nothing. | PASS (FR-008) |
| VII — Public-Safe | Output and errors are public-safe; provider selection never prints a credential. | PASS (FR-009, SC-004) |
| VIII — No SDK Replacement | No framework; argparse + the host. | PASS |
| IX — Reference, not clone | A terminal host re-derived for LoopPlane; no CLI implementation copied. | PASS |
| X — Testable Evolution | Tests + rollback (drop the entry point + package; default-unused = behavior-free revert). | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/017-loopplane-cli-host/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── cli.md                   # commands, exit codes, rendering, provider selection
│   └── integration-boundary.md  # how the CLI composes loopplane.host (V/VI)
└── tasks.md                     # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/cli/              # NEW subpackage
├── __init__.py                 # `main` console entry point + public surface (__all__)
├── app.py                      # argparse parser + command dispatch -> anyio.run
├── render.py                   # EventSink renderer: normalized events -> terminal (metadata-safe)
├── session.py                  # run_once + chat_loop core over LoopPlaneHost
└── providers.py                # select_model(env): scripted demo default; env-pointed real seam

pyproject.toml                  # [project.scripts] loopplane = "loopplane.cli:main"
examples/cli_quickstart.py      # drive the CLI core programmatically (credential-free)
docs/cli.md                     # the CLI guide

tests/unit/test_cli_render.py        # event rendering is metadata-safe
tests/unit/test_cli_providers.py     # provider selection (scripted default; gated real)
tests/integration/test_cli_us1.py..us5  # chat / run / sessions / provider / safe-thin
```

**Structure Decision**: Single library plus a console entry point. The CLI composes
only `loopplane.host`; its testable core (`app` dispatch, `session.run_once`,
`render`, `providers.select_model`) is exercised with a scripted model and captured
streams, and the interactive REPL is a thin wrapper over that core.

## Phases

- **Phase 0 — Research** (`research.md`): the `LoopPlaneHost` seam (`run` / `session` /
  `list_sessions` / `resume`), the `EventSink` rendering surface, the entry-point
  mechanism, provider selection, and credential-free testing.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): commands +
  exit codes, the renderer, provider selection, and the integration-boundary rules.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — renderer + provider unit tests first,
  then per-user-story integration, then the entry point + docs/example + packaging.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
