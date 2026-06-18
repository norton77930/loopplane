# Contract: Inspection Endpoints (read-only, metadata-only)

Four **additive** `GET` endpoints under the existing `/v1` web/API host, each behind the existing
auth boundary (`Depends(require)`), each backed by a `LoopPlaneHost` query method composing an
existing layer. **No tool is executed; no state is mutated** (Tool Gateway V + Event Bus VI
untouched).

## Endpoints

| Method + path | Host method | Response model | Notes |
|---|---|---|---|
| `GET /v1/inspect/skills` | `inspect_skills()` + `skill_problems` | `SkillsResponse { skills: SkillView[]; problems: string[] }` | loaded skills (metadata) + load problems (FR-001) |
| `GET /v1/inspect/tools` | `inspect_tools()` | `ToolView[]` | registered tools: name + descriptor (FR-002) |
| `GET /v1/inspect/mcp` | `inspect_mcp()` | `McpServerView[]` | connected MCP servers + their tools (FR-003) |
| `GET /v1/inspect/memory?q=…` | `inspect_memory(q)` | `MemoryEntryView[]` | memory entries (source + snippet); `q` filters via `select_entries` (FR-004) |

## Guarantees

1. **Read-only.** Every endpoint is a `GET` that reads already-loaded metadata and **executes no
   tool and mutates nothing** — the gateway is read via `descriptors()` only; no `invoke` path is
   reachable (FR-007 / SC-002).
2. **Metadata-only.** Responses contain only safe fields — skill `instructions`, MCP `args`/`url`,
   raw tool I/O, file contents, and secrets are **never** included; the memory `snippet` is a
   bounded `body` prefix (FR-007 / VII / SC-002). The projection lives in pure helpers
   (`inspect.py`), unit-tested to exclude risky fields.
3. **Auth-gated.** Each endpoint resolves the caller's `Principal` via `Depends(require)`; a request
   without/with-wrong credentials is rejected by the existing boundary (default-deny). Where the
   underlying data is principal-scoped it is scoped consistently (FR-008 / SC-002).
4. **Graceful empty state.** No skills / tools / MCP servers / memory (or no `memory_store`
   configured) → the endpoint returns an **empty list**, not an error; the panel shows an empty
   state (FR-009 / SC-003).
5. **Additive.** No change to the runtime core, the gateway, the event bus, or existing endpoints;
   `assemble()` only **retains** already-built references; the Python suite stays green (FR-010 /
   SC-004).

## Panel (web UI)

A tabbed `InspectionPanel` (Skills / Tools / MCP / Memory) as an optional right-side column in the
unit-025 shell, toggled from the header. Each tab fetches its endpoint on first view, lists the
results, and shows a clear empty state; the Memory tab adds a search box (re-fetch with `?q=`)
(FR-006 / FR-009). The panel is read-only — no execute/edit affordance.

## Verification

- `tests/unit/test_host_inspect.py`: the pure projection helpers — skills exclude `instructions`;
  tools project name/description/read_only/source; MCP groups `external-server:*` by server; memory
  bounds the snippet and filters by query; empty inputs → empty tuples.
- `tests/integration/test_webapi_inspection.py`: each endpoint is auth-gated (401/deny without a
  principal), returns metadata-only JSON, executes no tool (a spy gateway/handler is never invoked),
  and returns an empty list when the layer is absent.
- `apps/web` Vitest: `InspectionPanel` renders each tab's list + empty state and the memory search;
  the client methods call the right paths over a stubbed fetch.
