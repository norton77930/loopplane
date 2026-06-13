# Contract: Web / API Host boundary & audit

`loopplane.webapi` is an **additive transport** over the public host. This contract states the
boundary it must hold and the audit that enforces it (`tests/contract/test_webapi_boundary.py`).

## Allowed dependencies

The package imports **only**:

- `loopplane.host` — the public Host Application Interface (`LoopPlaneHost` / `build_host`,
  `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`, `ToolSpec`, …).
- `loopplane.events` — `EventSink`, `RuntimeEvent`, `serialize_event` (stream framing).
- `fastapi` / `starlette` — the web transport.
- The Python standard library and `pydantic` / `anyio` (already core deps).

It **must not** import:

- `loopplane.controller`, `loopplane.gateway`, `loopplane.dispatcher`, `loopplane.loop`, or any other
  runtime internal (reach-through past the host).
- Any sibling layer (`loopplane.engineering`, `scheduling`, `packs`, `review`, `recall`, `toolkit`,
  `governance`, `inspect`).

## Behavioral boundary

| Rule | Enforcement | Requirement |
|---|---|---|
| Drives runs **only** through `LoopPlaneHost.run` / `.session` / the `Session` handle | The package contains no loop/turn driving; it calls host methods | NFR-001, NFR-002 |
| **Executes no tool** | No gateway import; no tool resolve/authorize/execute path; a text scan finds no gateway/controller surface | Constitution V, NFR-002, SC-006 |
| **Re-emits no live bus**; consumes `on_event` only | The only event path is the injected `on_event` sink → `serialize_event` → SSE | Constitution VI, NFR-003, SC-006 |
| **Response bodies are metadata-only** | Response models expose no `ContentBlock` / tool I/O; history is `{role, block_count}` | FR-016, NFR-006, SC-003 |
| **Default-deny** auth | No injected authenticator ⇒ deny-all; missing/invalid/raising ⇒ deny | FR-014, NFR-005, SC-004 |
| **No outbound egress** of its own | No network client is constructed; only the embedded host is served | FR-017 |

## Audit (`test_webapi_boundary.py`)

An AST + text audit over `src/loopplane/webapi/*.py`, mirroring the Phase-3..10 boundary tests:

1. **Import allow-list** — every `loopplane.*` import is under `loopplane.host` or `loopplane.events`;
   0 violations (NFR-001).
2. **No runtime-internal names** — no import of a controller/gateway/dispatcher symbol; a text scan
   finds no `RuntimeController` / gateway-execute / `run_loop` token (NFR-002, SC-006).
3. **No tool execution** — the package never invokes a tool handler/adapter directly; tool execution
   is the gateway's, reached only via the host (Constitution V).
4. **Metadata-only responses** — a representative response projection (RunResult / history view) is
   asserted to carry only the declared metadata fields and no content block (FR-016, SC-003).
5. **Default-deny** — an app built with no authenticator denies a representative request (FR-014,
   SC-004).
6. **Determinism** — for a scripted run, the SSE frame order equals the recorded `serialize_event`
   order on repeat (NFR-004, SC-002).

## Public-safety scan (`PHASE11_TARGETS`)

`tests/contract/test_public_safety.py` is extended with the webapi package targets: committed
sources, the example, and the doc contain no secret, private path, internal name, or IP (Principle
VII, NFR-006, SC-003). The host's runtime **content** that flows on the live SSE stream is out of
scope for this committed-artifact scan — it is the authenticated client receiving the run's own
normalized output (Constitution VI), not a committed leak.
