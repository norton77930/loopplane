# Changelog

All notable changes to LoopPlane are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
Semantic Versioning.

## [0.1.0] - 2026-06-18

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
- **021** Checkpoint store backends — the checkpoint store is now a `CheckpointStore`
  interface (Protocol) with two interchangeable implementations: `FileCheckpointStore`
  (the unchanged default) and an optional `SqliteCheckpointStore` (standard-library
  `sqlite3`, no new dependency), selected via `StorageConfig(checkpoint_backend=...)`.
  Multi-user/`principal_id` and a networked database remain deferred.
- **022** Web principal authentication & per-principal session scoping
  (`loopplane.webapi`) — the web/API auth boundary now identifies the caller (a
  `Principal`) instead of only admitting/denying, and every session is scoped to the
  principal that opened it (the listing is filtered; a non-owner gets a `404`). The owner
  is recorded in the checkpoint metadata (`principal_id`) so scoping survives restarts,
  and a reference `token_authenticator` ships for dev/tests. **Breaking:** the web/API
  `Authenticator` return type changes from a bool to `Principal | None` (the unit-011
  web/API surface; embedders with a boolean verifier must return a principal or `None`).
  No new runtime dependency; the runtime core is unchanged.
- **023** Web frontend login UI (`apps/web`) — a login screen captures an access token and
  gates the single-page app over the unit-022 secured backend: the token is sent as a
  bearer credential, persisted in `sessionStorage` (cleared on tab close), and cleared on
  logout or an authorization failure (a 401 returns the user to login). Frontend only; the
  runtime and the existing unit-018 app are unchanged.
- **024** Desktop packaging (`apps/desktop`) — the Electron app can be packaged into a
  distributable installer that bundles a **PyInstaller-frozen** sidecar, so an end-user
  needs no system Python: a freeze spec, an electron-builder config, and a unit-tested
  spawn resolver that runs the bundled frozen sidecar in a packaged app and
  `python bridge.py` in development. Desktop-only; the runtime is unchanged; producing and
  signing the per-OS installer is a reserved manual / CI step.
- **025** Web agent UI (`apps/web`) — a frontend-only visual + UX overhaul of the
  single-page app into a modern agent UI: a two-pane shell (sessions sidebar + a chat
  column with a sticky header and composer), assistant **markdown** rendering (safe — no
  raw HTML), inline **collapsible tool cards** (running -> success/failure), styled
  approval/question dialogs, a run-status indicator + a **Stop** control, a non-blocking
  error banner, auto-scroll with jump-to-latest, a **light/dark theme** (persisted, system
  default), and a restyled login. The reducer now folds events into one **ordered entry
  list** so tool cards interleave with messages. Reuses the api layer + the unit-023 auth
  gate unchanged; no backend change.
- **026** Web agent signals (`apps/web`) — a frontend-only extension that surfaces three signals
  the backend **already emits** but the UI ignored: a distinct, de-emphasized, **collapsible
  thinking block** (`assistant-reasoning-increment`), **selectable question options** with a
  free-text fallback (the question payload's `text` + `options`; corrects the unit-018 `prompt`
  mis-mapping), and a **per-turn + session token-usage** indicator (`turn-completed`). Each
  degrades gracefully when its data is absent. No backend change.
- **027** Web agent inspection panels (`loopplane.host` / `loopplane.webapi` + `apps/web`) —
  additive, read-only, metadata-only inspection of the agent's capabilities/context: four
  `GET /v1/inspect/{skills,tools,mcp,memory}` endpoints (auth-gated) backed by `LoopPlaneHost`
  query methods that compose the existing skills / gateway / MCP / memory layers, rendered as a
  tabbed inspection panel in the web UI. MCP servers are derived from the `external-server:`
  descriptor source (never the config's args/url); no tool is executed and no state is mutated
  (the Tool Gateway and the Event Bus are untouched). No ADR.
- **028** Web agent model selection & file attachments (`loopplane.webapi` / `loopplane.host` +
  `apps/web`) — additive, web/API-layer, **no ADR**. A model catalog (`GET /v1/models`) of
  pre-configured single-model hosts sharing the unit-021 checkpoint root; runs/sessions accept a
  `model` id routed to the chosen host (one model per run). An upload endpoint
  (`POST /v1/uploads`, auth-gated, per-principal, size-limited) + a per-reference `UploadStore` +
  a `read_upload` Tool Gateway tool (`loopplane.host.upload_tool`) the agent calls to read a file
  on demand — transient input by id, never embedded into the content model. The composer gains a
  model selector + file attachments. The runtime, content model, Tool Gateway, and Event Bus are
  unchanged.

[0.1.0]: https://github.com/norton77930/loopplane/releases/tag/v0.1.0
