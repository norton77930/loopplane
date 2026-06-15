# Changelog

All notable changes to LoopPlane are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
Semantic Versioning.

## [0.1.0] - Unreleased

The initial LoopPlane line: a spec-first, embeddable agent-harness runtime and its
additive layers (units 001-013), brought to release quality by unit 014.

### Added

- **001** Runtime foundation — the agent loop, runtime controller, dispatcher, the
  tool gateway, internal and MCP tool adapters, skill execution profiles, the
  normalized runtime event bus, memory, checkpointing, artifact storage, the
  observability overlay, and the human-approval boundary.
- **002** Host interface (`loopplane.host`) — the Host Application Interface, a
  programmatic runtime configuration object, and a reference runner.
- **003** Loop engineering (`loopplane.engineering`) — loop definitions, the loop
  controller, triggers, validators, evaluators, retry/repair, reconstructable loop
  state, and loop events.
- **004** Scheduling (`loopplane.scheduling`) — the local scheduler and trigger
  engine with an injectable clock.
- **005** Validator & evaluator packs (`loopplane.packs`) — reusable validators and
  scoring evaluators.
- **006** Human review (`loopplane.review`) — human-review workflows over the
  approval boundary.
- **007** Memory recall & knowledge (`loopplane.recall`) — recall and knowledge
  indexing as loop-aware context sources.
- **008** Advanced tool gateway (`loopplane.toolkit`) — tool discovery, registry,
  packages, manifests, versioning, and diagnostics.
- **009** Sandbox, policy & governance (`loopplane.governance`) — sandbox, path,
  permission, budget, quota, and cost policies.
- **010** Observability & debug (`loopplane.inspect`) — read-only trace, timeline,
  replay, and diagnostics data contracts.
- **011** Web/API host (`loopplane.webapi`) — the web/API host transport.
- **012** Desktop/studio host (`loopplane.studio`) — the local desktop/studio host.
- **013** Multi-agent orchestration (`loopplane.orchestration`) — subagents, a
  coordinator, delegation, and aggregated event/artifact views.
- **014** Release packaging & docs — packaging metadata, a single-source version, a
  PEP 561 `py.typed` marker, the public API reference, the getting-started guide,
  docs and examples indexes, this changelog, the release-readiness checklist, and
  CI build verification.
- **020** Model-provider adapters (`loopplane.adapters.anthropic`,
  `loopplane.adapters.openai`) — real Anthropic and OpenAI adapters implementing the
  model boundary, each behind its own optional extra (`anthropic`, `openai`), with
  duck-typed stream mapping, offline stub-based tests, and an opt-in live check.

[0.1.0]: https://github.com/norton77930/loopplane
