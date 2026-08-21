# ADR 0017: The Desktop sidecar may import `loopplane.commands`

- **Status**: **Accepted** (2026-08-20) — the maintainer decided at the unit-083 Wave 6 boundary
  gate to admit the module and accepted this record at unit completion; this ADR records that
  boundary-definition update per Constitution VIII.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. It widens, by exactly one module, the sidecar
  import allow-list that ADR 0015 established and ADR 0016 (D5) last widened.
- **Related**: **ADR 0015** (Desktop cowork process/profile/presentation boundary), spec 065
  (backend slash commands), unit 083 FR-013/FR-016, Constitution **IV** (a boundary-blurring change
  updates the boundary definition), **V** (Gateway-only tool execution), **VI** (normalized events).

## Context

Unit 065 built `loopplane.commands`: a `CommandRegistry` that parses a leading-`/` line and answers
`/cost`, `/model`, `/memory`, and `/compact` from **existing public host seams**
(`session_cost`/`monthly_spend`, a wiring-supplied model list, `inspect_memory`,
`compact_session`). Commands are host **UX**, not tools: dispatch never reaches the Tool Gateway or
the Event Bus, never raises, and answers a fixed public-safe result. Two hosts already consume the
registry directly: the CLI chat REPL (`src/loopplane/cli/session.py`) and the web/API host's
`POST /commands` endpoint (`src/loopplane/webapi/app.py`).

Unit 083 (FR-013) brings the same commands to the Desktop composer. The Desktop sidecar is the
natural third consumer — it already holds the Host whose seams the handlers read — but the sidecar
boundary contract (`tests/contract/test_desktop_boundary.py::RUNTIME_ALLOWED_PREFIXES`) admits only
`loopplane.{host,events,errors,model,adapters}`, so the import is refused until the boundary
definition itself is updated. Implementing the registry a second time in the sidecar or the renderer
would fork the command semantics FR-013 exists to share.

## Decision

- **D1 — `loopplane.commands` joins `RUNTIME_ALLOWED_PREFIXES`.** The sidecar becomes the
  registry's third host-UX consumer, beside the CLI and the web/API host, using the same
  `default_registry()` and the same `CommandContext` shape.
- **D2 — the boundary's intent is unchanged.** The allow-list exists to keep the sidecar on public
  host facades and off stores, controllers, gateways, and tools. `loopplane.commands` satisfies that
  intent: its handlers call only public host methods, and only `/compact` mutates — through the
  loop's existing compaction seam, not through the Gateway. Constitution V (Gateway-only tool
  execution) and VI (no new events) are untouched; the prohibited-prefix list is unchanged.
- **D3 — the sidecar wires commands as one RPC method** (`command.execute`, unit 083 Wave 6) under
  the standing six-registry discipline, with the composer intercepting a leading `/` and rendering
  the normalized result locally — no model round-trip, no run, no Gateway, no Event Bus.

## Consequences

- The Desktop composer answers the four commands with CLI/Web-identical semantics from one shared
  implementation; a future command lands on all three surfaces at once.
- The sidecar's import surface grows by one module whose only reach is public host seams; the
  boundary test keeps proving the rest of the fence from source, including its negative self-check.
- Reverting is one line (drop the prefix) plus the Wave 6 code, restoring the 078 contract exactly.
