# LoopPlane documentation

Start with [Getting started](./getting-started.md); the full public surface is in
the [API reference](./api-reference.md).

## Getting started & the runtime

- [Getting started](./getting-started.md) — install, the smallest run, and where to go next.
- [Embedding quickstart](./quickstart.md) — the runtime foundation, hands-on (unit 001).
- [Host interface](./embedding-host.md) — embed through the host interface (unit 002).
- [Real-model validation](./real-model-validation.md) — the manual real-model procedure.

## Layer guides

- [Loop engineering](./loop-engineering.md) — loop definitions, triggers, validators, retry/repair (unit 003).
- [Scheduling](./scheduling.md) — the local scheduler and trigger engine (unit 004).
- [Validator & evaluator packs](./packs.md) — reusable validators and evaluators (unit 005).
- [Human review](./human-review.md) — human-review workflows over the approval boundary (unit 006).
- [Memory recall](./memory-recall.md) — recall and knowledge indexing as context sources (unit 007).
- [Advanced tool gateway](./tool-gateway-advanced.md) — discovery, registry, packages, manifests (unit 008).
- [Sandbox, policy & governance](./sandbox-policy-governance.md) — execution safety and governance (unit 009).
- [Observability & debug](./observability-debug.md) — read-only trace/timeline/diagnostics (unit 010).
- [Web / API host](./web-api-host.md) — the web/API host transport (unit 011).
- [Desktop / studio host](./desktop-studio-host.md) — the local desktop/studio host (unit 012).
- [Multi-agent orchestration](./multi-agent-orchestration.md) — subagents, coordinator, delegation (unit 013).
- [Lifecycle hooks](./hooks.md) — observe and gate the agent at lifecycle points (unit 015).
- [Plugins](./plugins.md) — manifest bundles packaging skills, MCP servers, and hooks (unit 016).
- [The `loopplane` CLI](./cli.md) — a thin terminal host over the host interface (unit 017).
- [Web frontend](./web-frontend.md) — a single-page UI over the web/API host (unit 018).
- [Desktop GUI](./desktop-gui.md) — a local Electron shell over a sidecar host (unit 019).
- [Model providers](./model-providers.md) — real Anthropic and OpenAI model adapters (unit 020).

## Reference

- [API reference](./api-reference.md) — every public package and name.

## Project

- [Capabilities](./capabilities.md) — the functional-scope overview of what LoopPlane provides today.
- [Gap analysis & roadmap](./gap-analysis.md) — comparison vs reference agent harnesses + the forward roadmap.
- [Roadmap autopilot board](./loopplane-agent-board.md) — the roadmap control document.
- [Release readiness](./release-readiness.md) — the pre-release gate checklist.
- [Manual QA](./manual-qa.md) — the human acceptance pass (browser, desktop, real model).

Runnable examples are catalogued in the [examples index](../examples/README.md).
