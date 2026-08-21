# LoopPlane Target Architecture Boundaries (Normative)

> This document operationalizes Principles IV–VI of `.specify/memory/constitution.md` into per-package rules. On conflict, the constitution wins.
> Language: **MUST / MUST NOT / SHOULD** are normative. An AI agent MUST stop and obtain human approval before violating any MUST(-NOT).

## 0. Global invariants (referenced as G# by the blocks below)

- **G1 — The Gateway is the single tool-execution point** (Constitution V). Every tool concern (registry, resolve, permission, execution, timeout, error normalization, size management) MUST sit behind `ToolGateway`. SPI = `describe()/invoke()/shutdown()` (`gateway/spi.py`); six stages: resolve → validate → decide → execute (60 s limit) → normalize → size-manage (64 KB). The Gateway is the only component that may call `.invoke()`.
- **G2 — Single event-bus owner** (Constitution VI). `EventSink` (`events/emitter.py`) is the runtime's only outbound seam. Consumers (webapi/studio/cli/inspect) MUST NOT re-emit the live bus. Event-schema (`SCHEMA_VERSION`) changes are versioned contract changes and MUST pass a human approval gate.
- **G3 — Persistence**. Checkpointing is append-only and its recording boundary is owned by `controller`; `ledger` is an atomic counter deliberately separate from checkpointing (ADR 0010); no other package may write session state on its own.
- **G4 — Optional dependencies**. Base deps are only anyio/pydantic/jsonschema. Exactly four sanctioned guard patterns: ① lazy import inside a function; ② injected client + TYPE_CHECKING; ③ package-level extra (only `webapi`); ④ env-gate + try/except ImportError (only `observability`). New extras MUST be maintainer-approved.
- **G5 — Default-off / byte-identity**. A new knob left unset MUST leave behavior byte-identical. Changing any default is a behavior change and MUST pass a human approval gate.
- **G6 — Layering**. Phase-1 runtime ← Phase-2 host ← Phase-3 engineering. Higher layers use only lower layers' public surfaces; `engineering.run_loop` is the only launch entry for Phase-3 features (scheduling/orchestration/review/recall).
- **G7 — Testing expectations**. Behavior changes MUST ship with tests (Constitution X); convention = `unit/test_<pkg>_core` + `contract/test_<pkg>_boundary` + `integration/test_<pkg>_us*`.
- **G8 — Docs expectations**. Public API changes update `docs/api-reference.md` within the same unit; significant capabilities SHOULD have an example (currently behind — see ARCHITECTURE_AUDIT.md §5).

## Block format

Each block covers: responsibility / allowed deps / forbidden deps / public API / internal-only / event-stream rules / tool-gateway rules / persistence rules / optional-dependency rules / testing expectations / docs & examples expectations / AI cautions. Shared rules are referenced as G# rather than repeated.

## 1. core runtime (`loop`, `model`, `gateway`, `events`, `context.py`, `errors.py`, `hooks`, `approval`, `budget`, `artifacts`, `checkpoint`, `memory`, `controller`, `fairness.py`)

- **Responsibility**: turn cycle, model boundary, the single tool chokepoint, normalized events, session records and lifecycle. `loop`'s three nevers: never persists / never formats / never authorizes.
- **Allowed deps**: intra-group along the existing directions (loop → model/gateway/events/context/budget/fairness/hooks; controller → checkpoint/events/context); base deps only.
- **Forbidden deps**: `tools` (as a runtime import; the TYPE_CHECKING-only exception exists solely in `context.py`), `adapters`, `host`, `webapi`, `studio`, any Phase-3 package, any SDK.
- **Public API**: each subpackage's `__all__` (see `docs/api-reference.md`).
- **Internal-only**: gateway stage implementations, `checkpoint/records.py` serde details, the sequencer, `BatchingSink` internals.
- **Event-stream rules**: only loop/controller emit events, via `EventEmitter` (G2).
- **Tool-gateway rules**: G1; approval/budget/fairness participate only as decide-stage / in-loop policies.
- **Persistence rules**: G3.
- **Optional-dependency rules**: `checkpoint/postgres.py` lazy psycopg (G4 ①).
- **Testing expectations**: G7; event/checkpoint schema changes MUST update contract tests in the same change.
- **Docs & examples**: G8; core behavior changes are recorded in the CHANGELOG.
- **AI cautions**: the TYPE_CHECKING-only import in `context.py` MUST NOT be converted to a top-level import; `SCHEMA_VERSION` / `RECORD_SCHEMA_VERSION` changes require a human gate first; changing a Protocol signature breaks tools + assembly + controller simultaneously.

## 2. host (`host`, `cli`, `commands`)

- **Responsibility**: the embedding seam (`LoopPlaneHost`/`RuntimeConfig`), the single composition root `assemble`, the CLI host (console script `loopplane`), and slash commands (unit 065, host UX).
- **Allowed deps**: all Phase-1 public surfaces; `host/assembly.py` is the **only** place allowed to (lazily) import concrete `tools` implementations and supervisor factories.
- **Forbidden deps**: `cli`/`commands` MUST NOT call gateway internals or `tools` directly; `commands` MUST NOT become a tool and MUST NOT bypass the Gateway/Event Bus.
- **Public API**: `LoopPlaneHost`, `RuntimeConfig`, `assemble`/`AssembledRuntime`, `CommandRegistry`/`default_registry`/`CommandDescriptor`/`format_command_listing`, `cli.main`, and (079) `cli.remote_loop`/`RemoteEndpoint`/`resume_loop` plus the `LineSource` input primitives.
- **Internal-only**: assembly wiring internals, `_resolve_permission_mode`.
- **Event-stream rules**: consume, never re-emit (G2). **Tool-gateway rules**: never execute tools (G1). **Persistence rules**: via controller (G3).
- **Optional-dependency rules**: the CLI defaults to a credential-free demo model and imports with base deps alone. Unit 079's remote bridge (`cli/remote.py`) lazily imports `httpx` from the pre-existing `net` extra (G4 ①), guarded so its absence is an explained state rather than an import error; a boundary test asserts `httpx` never appears at module import.
- **Testing expectations**: G7 (host/cli/commands each have core + boundary + US suites).
- **Docs & examples**: keep `docs/embedding-host.md` and `docs/cli.md` in sync.
- **AI cautions**: "tidying the imports of `assembly.py`" breaks the optional-extra boundary — the lazy imports are deliberate; new `RuntimeConfig` knobs MUST be default-off (G5).

## 3. webapi

- **Responsibility**: ASGI transport (HTTP/SSE/WS) over `LoopPlaneHost`; auth (token / JWT+JWKS, units 056/067); `EventReplayStore` (071); `TenantHostPool` (061); cost (064) and capability-management (075) endpoints.
- **Allowed deps**: `host` public surface, `commands`, `events` (serialization), fastapi/starlette (G4 ③, package-level).
- **Forbidden deps**: MUST NOT re-compose runtime internals, execute tools, or re-emit the live bus.
- **Public API**: `create_app`, `token_authenticator`/`jwt_authenticator`, `EventReplayStore`, `TenantHostPool`, plus the outward HTTP/SSE/WS contract. `apps/web` and `apps/desktop` depend on it through backend-owned generated types; since unit 079 `loopplane.cli`'s remote bridge is a **third consumer**, hand-written and in-repo — it reads routes, JSON keys, and the SSE frame grammar directly (ADR 0018). Its integration tests run against a real `create_app`, so same-tree drift breaks them; cross-release skew is not covered, which is why a contract change must consider the CLI as well as the two apps.
- **Internal-only**: streaming implementation, pool internals, JWKS resolver details.
- **Event-stream rules**: SSE/WS are pure transport; replay persistence belongs to the web boundary, not the `events` package.
- **Persistence rules**: replay-store backends; session state still flows through the controller (G3).
- **Optional-dependency rules**: `web` package-level; oauth (jwt/httpx) and postgres lazy (G4 ①).
- **Testing expectations**: unit + six web contract suites + ~18 integration suites.
- **Docs & examples**: `docs/web-api-host.md`; contract changes regenerate the shared types.
- **AI cautions**: `webapi/auth_jwt.py` (JWKS refresh throttle / negative-kid cache / single-flight; unit 067, default-ON) is security-sensitive and easy to weaken subtly; `webapi/app.py` is the route-aggregation hotspot — check pool/principal boundaries before adding routes; outward contract changes = human gate.

## 4. studio

- **Responsibility**: local desktop/studio dev host + `InProcessSidecar`; no GUI, no network service.
- **Allowed deps**: `host` public surface. **Forbidden deps**: runtime internals, network frameworks.
- **Public API**: `StudioHost`, sidecar types, view models. Everything else per G1–G3, G7.
- **AI cautions**: `apps/desktop` depends on the sidecar interface — changes require checking the desktop app in the same pass.

## 5. engineering (with `scheduling`, `packs`, `review`, `recall`, `orchestration`)

- **Responsibility**: the Phase-3 outer control loop (`run_loop`, `LoopDefinition`); trigger scheduling, validator/evaluator packs, human review flows, recall assembly, multi-agent composition.
- **Allowed deps**: the Host Interface (Phase-2 public surface) plus `engineering`'s own public surface.
- **Forbidden deps**: `orchestration` MUST NOT import `gateway`/`context`/`model` (audit grep: zero hits — keep it that way); the whole group MUST NOT import `tools`.
- **Public API**: `run_loop`, `LoopDefinition`, `Scheduler`, `Coordinator`, and the packs/review/recall public surfaces.
- **Event-stream rules**: owns its own loop/scheduler events; MUST NOT touch runtime-bus ownership (G2).
- **Tool-gateway rules**: never executes tools (G1). **Persistence rules**: via public surfaces (G3). **Optional-dependency rules**: none.
- **Testing expectations**: G7; **note**: `engineering` has the thinnest coverage relative to size (ARCHITECTURE_AUDIT.md §5) — SHOULD add tests before changing it.
- **AI cautions**: `run_loop` is the only launch entry; adding a "shortcut" that drives `AgentLoop` directly violates G6.

## 6. governance

- **Responsibility**: pure decide-stage policy deciders (permission / path / capability / budget / network / plan mode / sandbox profile / rule DSL / `modes.py` `PERMISSION_MODES`), all returning `PolicyVerdict`.
- **Allowed deps**: `approval` types, `context` types. **Forbidden deps**: `tools`; MUST NOT execute, resolve, or OS-sandbox a tool.
- **AI cautions**: a new policy MUST return `PolicyVerdict`, MUST be composable (combinators), and MUST be off by default (G5). Everything else per G1/G7.

## 7. tools

- **Responsibility**: built-in tool implementations of the gateway SPI (file/web/todo/notebook/undo/subagent/uploads/…), the supervisors (background/scheduling/messaging/worktree — implementing the `context.py` Protocols), and command executors (`LocalJailCommandExecutor`).
- **Allowed deps**: the gateway SPI, `model` types, `context` Protocols (as implementor), narrow Phase-1 public payload/store surfaces (`events.envelope` — only for the public event/question payload types tool adapters currently require; `memory.store` — only through the narrow public memory-store surface the memory tools currently use), the `engineering` public surface (`SpawnSubagentAdapter` goes through `run_loop`), the `orchestration` public surface (`aggregate_events`/`SubagentResult`/`ChildRunReference` — sanctioned by `specs/043-dynamic-subagents/contracts/spawn-subagent.md` for the dynamic-subagent path only), httpx lazy (G4 ①).
- **Forbidden deps**: MUST NOT be imported by `loop`/`controller`/`engineering` — the dependency direction is fixed as `host/assembly` → `tools`.
- **Public API**: `InternalToolAdapter` and the individual adapters/supervisors. **Internal-only**: executor details.
- **AI cautions**: this is the only package that knows both the Protocol implementations and the executables; note that `allowed_tools` drops a multi-tool adapter as a whole (a unit-043 review lesson); the only path for a new tool into the gateway is assembly injection. The tools → `orchestration` edge MUST stay narrow (the 043 dynamic-subagent path only — never a general dependency on orchestration internals) and MUST NOT be "fixed" by removing the import unless specs/043 is superseded; it is mechanically guarded by `tests/contract/test_tools_boundary.py`. Likewise the `events.envelope`/`memory.store` edges grant no ownership: tools MUST NOT own the runtime event bus, write checkpoint/session state, or bypass gateway-managed persistence boundaries (G2/G3), and these edges MUST NOT widen into general dependencies on events internals, checkpoint internals, controller internals, or persistence ownership. Everything else per G1/G5/G7.

## 8. adapters

- **Responsibility**: external model/tool-source integration (anthropic/gemini/openai/openai_compat/mcp).
- **Allowed deps**: `model` types, `errors`; SDKs only through injected clients (G4 ②).
- **Forbidden deps**: runtime internals; MUST NOT import an SDK at module top level (the package must import without any extra installed).
- **AI cautions**: cross-adapter alignment points — `provider_signature` (070), `cache_control` (040), `DocumentBlock` mapping (069); errors MUST be normalized to public-safe form (a unit-073 lesson).

## 9. toolkit

- **Responsibility**: offline tool-ecosystem organization **above** the Gateway (discover/catalog/manifest/version).
- **Forbidden**: MUST NOT execute any tool (G1).
- **AI cautions**: any proposal that "also lets the catalog execute" violates the constitution.

## 10. observability

- **Responsibility**: env-gated, metadata-only OTel overlay (`maybe_attach`).
- **Optional-dependency rules**: G4 ④ (`OTEL_EXPORTER_OTLP_ENDPOINT` gate + try/except ImportError).
- **AI cautions**: when unconfigured it MUST return the inner sink unchanged (G5); MUST NOT mutate or swallow events, and MUST NOT become a required path.

## 11. ledger

- **Responsibility**: per-`(principal_id, month)` USD accumulation, atomic and exact (`Decimal`); File/Sqlite/Postgres backends.
- **Forbidden**: merging with checkpointing; float arithmetic.
- **AI cautions**: Postgres `ON CONFLICT … RETURNING` is the only cross-process-atomic path (ADR 0010); the file backend uses sha256 keys.

## 12. pricing

- **Responsibility**: pure token-usage → USD conversion (`PricingTable`); enforces nothing.
- **AI cautions**: enforcement belongs to `budget` and MUST NOT be added to pricing.

## Appendix: remaining packages

`skills` (advertised/governed through the Gateway), `plugins` (directory composition of skills + MCP + hooks), `inspect` (read-only post-hoc diagnostics; an event consumer) — treated like toolkit/observability: never execute tools, never re-emit events, default-off.
