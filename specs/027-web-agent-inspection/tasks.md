---
description: "Task list for unit 027 — Web Agent Inspection Panels (additive, read-only, metadata-only)"
---

# Tasks: Web Agent Inspection Panels

**Input**: Design documents from `specs/027-web-agent-inspection/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/inspection-endpoints.md

**Tests**: REQUIRED (Constitution X). pytest (backend: pure projection helpers + webapi
integration) + Vitest/jsdom (frontend panel + client). Write tests FIRST and confirm they FAIL.

**Scope guard**: **additive, read-only, metadata-only**. Composes existing layers (skills loader /
`skill_problems`, `gateway.descriptors()`, MCP-via-descriptor-source, `MemoryStore`) via retained
references on `AssembledRuntime`; **no** runtime/gateway/bus/existing-endpoint change; **no** tool
execution or state mutation (V/VI untouched); **no** `instructions` / MCP `args`/`url` / raw I/O /
secrets. Both gates green at the implement commit. **No ADR.**

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency** — backend reuses the `web` extra (FastAPI/Pydantic);
  `apps/web` toolchain unchanged. Ensure deps are installed for both gates.

---

## Phase 2: Foundational (shared host inspection seam; tests first)

- [ ] T002 [P] Write `tests/unit/test_host_inspect.py` FIRST (FAIL): the pure projection helpers —
  `skills_view` excludes `instructions` and projects name/description/autonomous/approval/source;
  `tools_view` projects name/description/read_only/source; `mcp_view` groups `external-server:{name}`
  descriptors by server with their tool names; `memory_view` bounds the snippet and filters by query
  (`select_entries`); empty inputs → empty tuples.
- [ ] T003 Edit `src/loopplane/host/assembly.py`: add additive fields `gateway`, `skills`
  (`skills_map or {}`), `memory_store` to `AssembledRuntime` and set them from the values already
  built in `assemble()` (no behavior change — the un-inspected path is byte-identical).
- [ ] T004 Create `src/loopplane/host/inspect.py`: the frozen `SkillInfo`/`ToolInfo`/`McpServerInfo`/
  `MemoryEntryInfo` dataclasses + the **pure** helpers (`skills_view`, `tools_view`, `mcp_view`,
  `memory_view`, `SNIPPET_LIMIT`) per `data-model.md`. Make T002 pass.
- [ ] T005 Edit `src/loopplane/host/host.py`: add `inspect_skills()`, `inspect_tools()`,
  `inspect_mcp()`, `inspect_memory(query=None)` reading `self._assembled.{skills,gateway,memory_store}`
  and delegating to `inspect.py` (memory → `()` when `memory_store is None`).

**Checkpoint**: the host exposes metadata-only inspection; the full pytest suite still passes.

---

## Phase 3: User Story 1 - See the agent's skills and tools (Priority: P1) 🎯 MVP

**Goal**: read-only endpoints + panel tabs for loaded skills (with load problems) and registered
tools.

**Independent Test**: `GET /v1/inspect/skills` returns skills + problems; `GET /v1/inspect/tools`
returns tools; both auth-gated + metadata-only + execute no tool; the panel lists them with empty
states.

- [ ] T006 [P] [US1] Write `tests/integration/test_webapi_inspection.py` FIRST (FAIL) for
  `/v1/inspect/skills` and `/v1/inspect/tools`: each is **auth-gated** (denied without a principal),
  returns **metadata-only** JSON (no `instructions`), **executes no tool** (a spy handler is never
  invoked), and returns an empty result when nothing is configured.
- [ ] T007 [US1] Edit `src/loopplane/webapi/models.py` (add `SkillView`, `SkillsResponse`,
  `ToolView` + `from_*`) and `src/loopplane/webapi/app.py` (add `GET /inspect/skills` →
  `SkillsResponse{ skills, problems }`, `GET /inspect/tools` → `list[ToolView]`, each
  `Depends(require)`). Make the skills/tools cases of T006 pass.
- [ ] T008 [P] [US1] Frontend: extend `apps/web/src/api/types.ts` (`SkillView`, `SkillsResponse`,
  `ToolView`) and `apps/web/src/api/client.ts` (`inspectSkills()`, `inspectTools()` →
  `GET /v1/inspect/...`).
- [ ] T009 [US1] Frontend: create `apps/web/src/components/InspectionPanel.tsx` (a tabbed right-side
  panel with **Skills** + **Tools** tabs, fetch-on-view, list + **empty state**, skills show load
  problems); add an optional right-side panel slot to `apps/web/src/components/AppShell.tsx`; wire a
  header toggle + the panel in `apps/web/src/App.tsx`. Add
  `apps/web/src/__tests__/InspectionPanel.test.tsx` (Skills/Tools render + empty state over a stubbed
  client).

**Checkpoint**: a user opens the panel and sees skills (with problems) + tools.

---

## Phase 4: User Story 2 - See connected MCP servers (Priority: P2)

**Goal**: a read-only endpoint + tab listing connected MCP servers and their tools.

**Independent Test**: `GET /v1/inspect/mcp` lists servers (derived from `external-server:*` tool
sources) + their tools; empty when none; the MCP tab renders them.

- [ ] T010 [US2] Backend: add `McpServerView` + `GET /inspect/mcp` → `list[McpServerView]`
  (`Depends(require)`) and an integration case (servers + tools; empty when none; no config
  `args`/`url` in the payload). Frontend: `inspectMcp()` in the client + an **MCP** tab in
  `InspectionPanel` (list servers + their tools; empty state). Extend the panel test.

**Checkpoint**: connected MCP servers + their tools are inspectable.

---

## Phase 5: User Story 3 - Browse and search memory (Priority: P3)

**Goal**: a read-only endpoint + tab to list/search memory entries (source + snippet).

**Independent Test**: `GET /v1/inspect/memory` lists entries; `?q=` filters them; empty when none;
the Memory tab lists + searches.

- [ ] T011 [US3] Backend: add `MemoryEntryView` + `GET /inspect/memory?q=` → `list[MemoryEntryView]`
  (`Depends(require)`; `inspect_memory(q)`; bounded snippet; empty when no `memory_store`) and an
  integration case (list + query-filter + empty). Frontend: `inspectMemory(query?)` in the client +
  a **Memory** tab in `InspectionPanel` (list source + snippet; a search box re-fetches with `?q=`;
  empty state). Extend the panel test.

**Checkpoint**: memory entries are browsable + searchable, metadata-only.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T012 [P] Docs: `docs/web-api-host.md` (+ an inspection-endpoints section) and
  `docs/web-frontend.md` (+ an inspection-panels section).
- [ ] T013 [P] `CHANGELOG.md`: add a `027` entry under Added.
- [ ] T014 [P] `docs/loopplane-agent-board.md`: set **027 → Verified** with a status-evidence note;
  advance §3/§4 to make **028** the active unit.
- [ ] T015 Run the gates: **`pytest`** (full suite green — additive, SC-004) incl. the new unit +
  integration tests; `apps/web` `npm run typecheck` + `npm test` + `npm run build` green;
  public-safety scan clean (no secret/path/internal name; **no `instructions` / MCP `args`/`url` /
  raw I/O** in any payload; no legacy UI copied — VII).
- [ ] T016 Final review: confirm **additive** (runtime/gateway/bus/existing endpoints unchanged),
  **read-only + metadata-only** (no tool executed, no mutation), auth-gated, and the rollback (drop
  the endpoints/panel + retained references); commit (`feat: implement LoopPlane web-agent-inspection`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T005)** precede the stories (the host seam).
- **US1 (T006–T009)** is the MVP (skills + tools): webapi + panel.
- **US2 (T010)** depends on the host `inspect_mcp` (T005) + the panel (T009).
- **US3 (T011)** depends on the host `inspect_memory` (T005) + the panel (T009).
- **Polish (T012–T016)** depends on all three stories; both gates run green before the commit.

### Within each story / parallel opportunities

- Tests first and FAIL before implementation (T002, T006).
- T002 (helper tests) and T008 (frontend types/client) are independent `[P]`; docs T012/T013/T014
  are independent `[P]` files.
- Backend (host/webapi) and frontend (client/panel) within a story can proceed in parallel once the
  contract (this unit's `contracts/`) is fixed.

---

## Implementation Strategy

MVP = US1 (skills + tools — the highest-value inspection). Then US2 (MCP) → US3 (memory) → polish.
Each story is additive and independently testable; the metadata-only/read-only guarantee is enforced
in the pure projection helpers (one auditable place).

## Notes

- The host reads existing layers through **retained references** on `AssembledRuntime` (no controller
  reach-through; boundary IV). MCP servers derive from the tool descriptors' `external-server:{name}`
  source — the MCP config's secret-bearing `args`/`url` are never read (FR-007).
- **Read-only**: the gateway is read via `descriptors()` only; no `invoke`/mutation path is added
  (V/VI untouched).
- **Rollback**: drop the four endpoints + `InspectionPanel` + `inspect.py` + the additive
  `AssembledRuntime` fields → the runtime and prior UI are unaffected (X).
