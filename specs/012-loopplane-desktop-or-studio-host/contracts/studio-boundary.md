# Contract: Desktop / Studio Host boundary & audit

`loopplane.studio` is an **additive local presentation** over the public host. This contract states the
boundary it must hold and the audit that enforces it (`tests/contract/test_studio_boundary.py`).

## Allowed dependencies

The package imports **only**:

- `loopplane.host` — the public Host Application Interface (`LoopPlaneHost` / `build_host`,
  `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`, …).
- `anyio` — the task group that holds interactive sessions open (already a core dependency).
- The Python standard library.

It **must not** import:

- `loopplane.events` — the studio projects `RunOutcome`, not the live event stream; the discard sink it
  passes to `host.run` is typed `object`, so no event type is named.
- `loopplane.controller`, `loopplane.gateway`, `loopplane.dispatcher`, `loopplane.loop`, or any other
  runtime internal (reach-through past the host).
- Any sibling layer (`loopplane.engineering`, `scheduling`, `packs`, `review`, `recall`, `toolkit`,
  `governance`, `inspect`, `webapi`).

## Behavioral boundary

| Rule | Enforcement | Requirement |
|---|---|---|
| Drives runs **only** through `LoopPlaneHost.run` / `.session` / the `Session` handle | The package contains no loop/turn driving; it calls host methods | NFR-001, NFR-002 |
| **Executes no tool** | No gateway import; no tool resolve/authorize/execute path; a text scan finds no gateway/controller surface | Constitution V, NFR-002, SC-005 |
| **Re-emits no live bus** | The only event path is a discard sink; no `EventEmitter` / `.emit(` / `serialize_event` reference | Constitution VI, NFR-003, SC-005 |
| **View models are metadata-only** | View models expose no `ContentBlock` / tool I/O; history is `{role, block_count}` | FR-030, NFR-006, SC-003 |
| **No network / no OS process** | No socket, no `subprocess` / `os.system` / process-spawn import | FR-051, NFR-006 |

## Audit (`test_studio_boundary.py`)

An AST + text audit over `src/loopplane/studio/*.py`, mirroring the Phase-3..11 boundary tests:

1. **Import allow-list** — every `loopplane.*` import is under `loopplane.host`; 0 violations
   (NFR-001).
2. **No runtime-internal / event / sibling names** — a text scan finds no `loopplane.events` /
   `loopplane.controller` / `loopplane.gateway` / `loopplane.dispatcher` / `RuntimeController` /
   `EventEmitter` / `serialize_event` / sibling-package token (NFR-002, NFR-003, SC-005).
3. **No process spawn / network** — a text scan finds no `subprocess` / `os.system` / `socket` token
   (FR-051, NFR-006).
4. **Metadata-only views** — a representative view (`RunResultView` / history view) carries only the
   declared metadata fields and no content block (FR-030, SC-003).
5. **Conflict / fail-safe** — a concurrent run and a stopped sidecar return explicit views, not crashes
   (FR-003, FR-041, SC-004).

## Public-safety scan (`PHASE12_TARGETS`)

`tests/contract/test_public_safety.py` is extended with the studio package targets: committed sources,
the example, and the doc contain no secret, private path, internal name, or IP (Principle VII, NFR-006,
SC-003).
