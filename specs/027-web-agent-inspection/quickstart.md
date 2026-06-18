# Quickstart: Web Agent Inspection Panels

Validates the additive, read-only inspection endpoints + panels and proves both gates stay green.

## Prerequisites

- The Python `web` extra installed (FastAPI/Pydantic — already used by unit 011); the `apps/web`
  toolchain installed. **No new dependency.**
- A host configured with some skills / tools / MCP servers / memory for manual QA (the automated
  tests use a configured host + a stubbed fetch).

## Automated gates (authoritative)

```bash
# Backend
pytest tests/unit/test_host_inspect.py tests/integration/test_webapi_inspection.py
pytest                # full suite stays green (additive — SC-004)

# Frontend
cd apps/web
npm run typecheck && npm test && npm run build
```

## Manual QA (against a live host)

1. **Skills** — open the Inspection panel → **Skills** tab: loaded skills are listed (name +
   descriptor) and any **load problem** is surfaced; no `instructions` are shown (FR-001/007).
2. **Tools** — **Tools** tab: each registered tool is listed by name + short descriptor (FR-002).
3. **MCP** — **MCP** tab: each connected MCP server is listed with the tools it exposes; with none
   configured, a clear empty state (FR-003/009).
4. **Memory** — **Memory** tab: entries list with a source + snippet; typing a query filters them;
   with none, an empty state (FR-004/009).
5. **Read-only / metadata-only** — no panel offers an execute/edit action; no secret, raw tool I/O,
   or file content appears; an unauthenticated request to any `/v1/inspect/*` is rejected
   (FR-007/008, SC-002).

## Expected outcome

All four panels render (or show empty states); every endpoint is auth-gated and metadata-only and
executes no tool (SC-001/002/003); the change is additive — the runtime core, gateway, event bus,
and existing endpoints are unchanged and the Python suite is green (SC-004); the `apps/web` gate is
green (SC-005); a public-safety scan is clean (SC-006).

## Rollback

Drop the four endpoints + the `InspectionPanel` (and the additive `AssembledRuntime` references +
`inspect.py`). The runtime, the existing endpoints, and the prior UI are unaffected (Constitution X).
