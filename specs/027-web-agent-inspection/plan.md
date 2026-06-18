# Implementation Plan: Web Agent Inspection Panels

**Branch**: `027-web-agent-inspection` (main-only) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/027-web-agent-inspection/spec.md`

## Summary

Make the agent's **capabilities and context** inspectable from the web UI — **additive,
read-only, metadata-only**. The data already lives inside the runtime; this unit exposes it
through **new host query methods** that compose the **existing** internal layers (grounded in a
backend audit), four **read-only** web/API endpoints behind the existing auth boundary, and
**read-only inspection panels** (a tabbed right-side panel) in the unit-025 shell.

Backend (additive, no boundary crossed): `assemble()` **retains** the already-constructed
`gateway`, `skills` map, and `memory_store` on `AssembledRuntime` (additive fields — no behavior
change); `LoopPlaneHost` gains four metadata-only query methods backed by pure projection helpers
(`loopplane/host/inspect.py`):

- **Skills** — `inspect_skills()` projects each `LoadedSkill` to `{ name, description,
  autonomous, approval_required, source }` (never `instructions`); load problems reuse the
  existing `host.skill_problems`.
- **Tools** — `inspect_tools()` projects `gateway.descriptors()` to `{ name, description,
  read_only, source }`.
- **MCP** — `inspect_mcp()` derives connected servers + their tools from the tool descriptors
  whose `source` is `external-server:{name}` (so it reads **only** safe descriptor metadata, never
  the MCP config's `args`/`url`).
- **Memory** — `inspect_memory(query)` projects `MemoryStore.list_entries()` to
  `{ type, name, description, snippet }` (a bounded `body` snippet), filtered by the existing
  `select_entries` when a query is given.

Four `GET /v1/inspect/{skills,tools,mcp,memory}` endpoints (Pydantic view models, `Depends(require)`)
return these; the frontend adds a tabbed `InspectionPanel` (right-side, toggled from the header)
with per-tab fetch, empty states, and a memory search box. **No tool is executed and no state is
mutated** (Tool Gateway V + Event Bus VI untouched); the runtime core and existing endpoints are
unchanged; the Python suite and the `apps/web` gate stay green. **No ADR** (strictly additive —
confirmed by the audit and the spec).

## Technical Context

**Language/Version**: Python 3.12 (runtime/host/webapi) + TypeScript 5.6 / React 18 (`apps/web`).

**Primary Dependencies**: backend — none new (FastAPI/Pydantic already in the `web` extra; composes
existing `loopplane.{skills,gateway,adapters.mcp,memory}`). Frontend — none new (reuses the 025/026
toolchain).

**Storage**: none new. Memory entries come from the already-configured `MemoryStore` (file-backed);
skills/tools/MCP are in-memory runtime state.

**Testing**: pytest (backend) — pure projection-helper unit tests (`inspect.py`); webapi
integration tests (each endpoint: auth-gated, metadata-only, executes no tool, empty-state). Vitest
+ jsdom (frontend) — the `InspectionPanel` (tabs, lists, empty states, memory search) + the new
client methods over a stubbed fetch.

**Target Platform**: the web/API host (unit 011) + the browser SPA (unit 018/025).

**Project Type**: full-stack but **additive** — new host query methods + webapi read endpoints +
web panels; the runtime core, gateway, event bus, and existing endpoints are untouched.

**Performance Goals**: inspection is O(n) over already-loaded metadata; large lists scroll/paginate
in the panel. No hard numeric target.

**Constraints**: **metadata-only** — never `instructions`, MCP `args`/`url`, raw tool I/O, file
contents, or secrets (FR-007); **read-only** — no execution, no mutation (V/VI untouched, FR-007);
**auth-gated** — `Depends(require)`, principal scoping where the data is principal-scoped (FR-008);
**additive** — no runtime/gateway/bus/existing-endpoint change, Python suite green (FR-010); no
secret or legacy UI committed (FR-011 / VII).

**Scale/Scope**: ~1 additive assembly change (retain 3 references) + 1 new host submodule
(`inspect.py`) + 4 host methods + 4 webapi view models + 4 routes + 1 `InspectionPanel` + 4 client
methods + tests + docs/board. Three user stories P1–P3.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS** (no ADR).*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–011; SC-001–006), grounded in a backend audit. | PASS |
| II — Greenfield | New host/webapi/UI code written fresh; no legacy UI copied (VII). | PASS |
| III — Harness before automation | Read-only inspection; no loop automation; no model switching (deferred). | PASS |
| IV — Boundary Clarity | Reads existing layers through retained references on `AssembledRuntime` (no reach-through into controller privates); a new additive host seam. | PASS |
| V — Tool Gateway Ownership | **Reads** `gateway.descriptors()` only — **executes no tool**; no bypass path added. | PASS |
| VI — Event Bus Ownership | No event emitted/consumed; inspection is a separate read path, not the bus. | PASS |
| VII — Public-Safe | Metadata-only projections exclude `instructions` / MCP `args`/`url` / `body`-beyond-snippet / secrets; design fresh. | PASS |
| VIII — No SDK Replacement | No framework/runtime change. | PASS |
| IX — Reference, not clone | A conventional inspection panel, derived for this app. | PASS |
| X — Testable Evolution | Pure projection tests + webapi integration + panel tests; **rollback** = drop the endpoints/panel + the retained references (additive). | PASS |

No violations — Complexity Tracking is intentionally empty. **No ADR** is required: the unit is
strictly additive and crosses no runtime boundary (V/VI untouched), unlike model switching /
file upload (unit 028's ADR-adjacent items — themselves re-scoped additive).

## Project Structure

### Documentation (this feature)

```text
specs/027-web-agent-inspection/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── inspection-endpoints.md   # the 4 read-only endpoints + host query methods + metadata-only/read-only guarantees
├── checklists/requirements.md
└── tasks.md                       # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/host/
├── assembly.py        # EDIT — retain gateway, skills, memory_store on AssembledRuntime (additive fields)
├── inspect.py         # NEW — metadata-only dataclasses + pure projection helpers (skills/tools/mcp/memory)
└── host.py            # EDIT — inspect_skills() / inspect_tools() / inspect_mcp() / inspect_memory(query) (read self._assembled)

src/loopplane/webapi/
├── models.py          # EDIT — SkillView / ToolView / McpServerView / MemoryEntryView (+ from_* projections)
└── app.py             # EDIT — GET /inspect/skills, /inspect/tools, /inspect/mcp, /inspect/memory (Depends(require))

tests/ (backend)
├── unit/test_host_inspect.py            # NEW — pure projection helpers (metadata-only; secrets excluded)
└── integration/test_webapi_inspection.py # NEW — 4 endpoints: auth-gated, metadata-only, no-tool-exec, empty-state

apps/web/src/
├── api/
│   ├── types.ts       # EDIT — SkillView, ToolView, McpServerView, MemoryEntryView
│   └── client.ts      # EDIT — inspectSkills() / inspectTools() / inspectMcp() / inspectMemory(query?)
├── components/
│   ├── InspectionPanel.tsx   # NEW — tabbed right-side panel (Skills/Tools/MCP/Memory) + empty states + memory search
│   └── AppShell.tsx          # EDIT — optional right-side panel slot
└── App.tsx            # EDIT — toggle + wire the InspectionPanel to the client
```

Edited (docs / drift): `docs/web-api-host.md` (+ an inspection-endpoints section), `docs/web-frontend.md`
(+ an inspection-panels section), `CHANGELOG.md` (027 entry), `docs/loopplane-agent-board.md`
(027 → Verified; advance §4 to 028), `CLAUDE.md` (SPECKIT marker → 027 plan).

**Structure Decision**: The data sources are reached **only** through references the host already
owns: `assemble()` already builds the `gateway`, `skills` map, and `memory_store`, so retaining them
on `AssembledRuntime` (additive fields) gives the host a clean, boundary-respecting read path —
no reach-through into controller privates and no new runtime capability. Projection is a set of
**pure functions** in `inspect.py` (independently unit-testable, and the place the metadata-only
filtering lives), so the host methods and webapi stay thin. MCP servers are derived from the
**tool descriptors' `source`** (`external-server:{name}`), which avoids touching the MCP config's
secret-bearing `args`/`url` entirely. The frontend panel is purely additive in the 025 shell.

## Phases

- **Phase 0 — Research** (`research.md`): the audited source APIs (skills loader / `skill_problems`,
  `gateway.descriptors()`, MCP-via-descriptor-source, `MemoryStore.list_entries` + `select_entries`);
  the retain-on-`AssembledRuntime` decision (vs. reaching into controller privates); the
  metadata-only field selection (exclude `instructions`, MCP `args`/`url`, full `body`); the
  MCP-from-source derivation; and the no-ADR justification.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the host inspection
  dataclasses (`SkillInfo`, `ToolInfo`, `McpServerInfo`, `MemoryEntryInfo`) + the webapi view models;
  the endpoint contract (paths, auth, metadata-only/read-only guarantees, empty-state); and a
  quickstart driving the endpoints + the panel.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD, P1 → P3 — pure projection helpers + tests; assembly
  retain + host methods; webapi view models + routes + integration tests; frontend client + types +
  `InspectionPanel` + AppShell slot + App wiring; docs/board; the Python + web gates.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
