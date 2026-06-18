# Phase 0 Research: Web Agent Inspection Panels

All decisions are grounded in a read-only backend audit of the actual layer APIs. No
`[NEEDS CLARIFICATION]` markers; the open items were how to compose the existing layers safely.

## R1 — The audited source APIs (grounded)

| Source | Module | Read API | Safe metadata fields |
|---|---|---|---|
| Skills | `loopplane.skills` | `LoadedSkill { skill: Skill, source }`; `Skill { name, description, instructions, profile }`; `ExecutionProfile { autonomous_invocation, approval_required }`; problems = `list[str]` (already `host.skill_problems`) | name, description, autonomous, approval_required, source — **never** `instructions` |
| Tools | `loopplane.gateway` | `ToolGateway.descriptors() -> list[ToolDescriptor]`; `ToolDescriptor { name, description, input_schema, read_only, concurrency_safe, source }` | name, description, read_only, source (all safe) |
| MCP | `loopplane.adapters.mcp` | tools register through the gateway with `source = "external-server:{name}"` and qualified `name = "{server}:{tool}"` | derive server + tools from descriptor `source` — **never** the config `args`/`url` |
| Memory | `loopplane.memory` | `MemoryStore.list_entries() -> list[MemoryEntry]`; `MemoryEntry { type, name, description, body }`; `select_entries(entries, prompt, limit)` (search) | type, name, description, bounded `body` snippet |

## R2 — Reach the sources through `AssembledRuntime`, not controller privates

- **Decision**: `assemble()` already constructs the `gateway`, the `skills` map, and the
  `memory_store`; **retain** them as **additive fields** on `AssembledRuntime`
  (`gateway`, `skills`, `memory_store`). The host reads `self._assembled.{gateway,skills,memory_store}`.
- **Rationale**: a clean, boundary-respecting read path (Constitution IV) — no reach-through into
  `controller._gateway` / `._skills` / `._memory_store` (private). Additive: the fields are set from
  values already built in the same function; nothing else changes, so the un-inspected path is
  byte-identical and the Python suite stays green (FR-010).
- **Alternatives considered**: reading controller privates (boundary violation); a global registry
  (unnecessary state). Rejected.

## R3 — Metadata-only projection (the safety boundary, FR-007)

- **Decision**: projection happens in **pure functions** in `loopplane/host/inspect.py`, which select
  **only** safe fields:
  - skills → `{ name, description, autonomous, approval_required, source }` (drops `instructions`,
    flagged risky by the audit).
  - tools → `{ name, description, read_only, source }`.
  - MCP → group tool descriptors with `source.startswith("external-server:")` by server name; each
    server's tools are the descriptor names (no config `args`/`url` read).
  - memory → `{ type, name, description, snippet }` where `snippet` is `body` truncated to a bounded
    length (the recall snippet; full `body` is not dumped).
- **Rationale**: keeping the field selection in one pure, unit-tested place makes the metadata-only
  guarantee auditable and regression-proof. No secret, credential, raw tool I/O, file content, or
  private path can appear (FR-007 / SC-002 / VII).

## R4 — MCP servers derived from descriptor source

- **Decision**: list MCP servers + their tools by grouping `gateway.descriptors()` on the
  `external-server:{name}` `source` prefix — server name = the suffix, tools = those descriptors.
- **Rationale**: the connected servers + exposed tools are exactly what registered, and the
  descriptor `source`/`name` are safe metadata; this avoids touching `MCPServerConfig` (whose
  `args`/`url` may carry secrets) entirely (FR-003/007). A server configured but not connected simply
  has no descriptors → not listed (acceptable for "connected"); the empty case yields an empty panel
  (FR-009).

## R5 — Read-only, auth-gated, additive

- Endpoints are `GET /v1/inspect/{skills,tools,mcp,memory}` with `Depends(require)` (the existing
  022 auth boundary; default-deny) — **no execution, no mutation** (V/VI untouched, FR-007/008).
- The change is **additive**: no runtime/gateway/bus/existing-endpoint edit; existing tests stay
  green (FR-010). **No ADR** — the unit crosses no constitution boundary (unlike model switching /
  file upload).

## R6 — Frontend panel

- **Decision**: a tabbed `InspectionPanel` (Skills / Tools / MCP / Memory) as an optional right-side
  column in the 025 `AppShell`, toggled from the header; each tab fetches on first view via new
  `ApiClient` methods, renders a list with an **empty state**, and the Memory tab adds a search box
  (re-fetch with `?q=`). No new dependency.
- **Rationale**: additive to the 025 shell; read-only; reuses the existing client + styling.

**Output**: all choices resolved against the audited APIs; no open clarifications.
