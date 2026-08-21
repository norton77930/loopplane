# ADR 0018: The terminal host is a consumer of the web/API contract

- **Status**: **Accepted** (2026-08-21) — raised by the unit-079 architecture review; the
  maintainer accepted the terminal host as a third consumer of the outward web/API contract at
  the close of unit 079.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. It amends the Block 2 and Block 3
  descriptions in `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`.
- **Related**: **ADR 0015/0016/0017** (each records a comparable widening of what a host may
  reach), unit 079 (CLI and remote parity), Constitution **IV** (a change that blurs a boundary
  updates the boundary definition), **V**, **VI**.

## Context

Before unit 079, `loopplane.cli` was described as a thin host over `loopplane.host`: it composed
the Host Application Interface and rendered normalized events, and its only outward dependency was
the Python API. The outward HTTP/SSE/WS contract belonged to Block 3, whose stated consumers were
`apps/web` and `apps/desktop`, both depending on it through backend-owned generated types.

Unit 079 added `loopplane.cli.remote`, which drives a conversation on a LoopPlane web/API host by
being a client of the endpoints that host already exposes. The unit changed no endpoint, field, or
frame format — but it made the terminal a third consumer of that contract, and unlike the two
applications it reads the contract by hand: the `/v1` prefix (now overridable), the route shapes,
the request and response JSON keys, and the SSE frame grammar (`id:` / `data:`) are written into
`remote.py` rather than generated.

The unit-079 review also demonstrated that this is not merely a documentation gap. The shared
`CommandRegistry` is a delivery channel *into* the web host: adding two session-scoped commands to
it made them reachable through `POST /v1/commands` without the ownership gate that route applies,
which was a cross-principal disclosure. The relationship between Block 2 and Block 3 is therefore
load-bearing in both directions, and was previously written down in neither.

## Decision

- **D1 — the terminal is a first-class consumer of the outward web contract.** Block 3's public API
  description names `loopplane.cli` alongside `apps/web` and `apps/desktop`. A change to a route,
  a field, or the SSE framing must consider the terminal, which has no generated types to fail
  loudly at build time.
- **D2 — the coupling stays hand-written, and is defended by tests rather than by codegen.**
  Generating types for a Python client would introduce a build step the project does not have, for
  one consumer. Instead the remote client's integration tests run against a real `create_app` over
  an in-process transport, so any same-tree contract drift breaks them. Cross-release skew (a newer
  terminal against an older server) remains uncovered and is accepted as a known limitation.
- **D3 — the command surface declares what hosts must gate.** `CommandRegistry` marks each command
  `session_scoped`, and a host with principals reads `session_scoped_names()` rather than keeping
  its own list. Adding a command can no longer silently bypass a host's ownership check. **Every**
  session-scoped handler — including the two that predate this unit, and notably `/compact`, the
  only irreversible one — additionally refuses a conversation the caller does not own, so a host
  that skips the gate degrades to "not found" instead of disclosing. The two ownership predicates
  differ deliberately: the web host treats a principal-less session as nobody's, while the command
  layer treats it as readable, because a host without principals (the terminal, the desktop
  sidecar) owns its own conversations. That divergence is safe exactly while the gate covers every
  scoped command, which a test pins directly.
- **D4 — the CLI's optional-dependency rule is amended.** Block 2 said the CLI had none; the remote
  bridge lazily imports `httpx` from the pre-existing `net` extra under guard pattern G4 ①. No new
  dependency and no new extra were introduced, and the terminal still imports and runs with base
  dependencies alone.

## Consequences

- The boundary document now describes what the code does, and a future contract change has an
  accurate list of who depends on it.
- The ownership rule for commands lives with the commands, which is what makes the disclosure class
  of defect structurally hard to repeat rather than merely fixed once.
- The terminal remains exposed to cross-release contract skew: an older server answers 404 for a
  route the terminal expects, which the client currently reports as "the conversation is no longer
  available". Version signalling is deliberately out of scope here and is recorded as a follow-up.
- Reverting is bounded: dropping `cli/remote.py` and its tests restores the pre-079 Block 2/3
  relationship exactly, and the boundary text reverts with it.
