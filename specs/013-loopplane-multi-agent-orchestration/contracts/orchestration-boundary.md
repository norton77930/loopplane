# Contract: Multi-Agent Orchestration boundary & audit

`loopplane.orchestration` is an **additive orchestration** over the public Phase-3 loop surface. This
contract states the boundary it must hold and the audit that enforces it
(`tests/contract/test_orchestration_boundary.py`).

## Allowed dependencies

The package imports **only**:

- `loopplane.engineering` — the public Phase-3 loop surface (`run_loop`, `LoopDefinition`,
  `LoopOutcome`, `LoopEvent`, `LoopState`, `RunReference`, `ArtifactRef`).
- The Python standard library.

It **must not** import:

- `loopplane.host`, `loopplane.controller`, `loopplane.gateway`, `loopplane.dispatcher`,
  `loopplane.events`, `loopplane.loop`, or any other Phase-1/2 runtime internal (reach-through past the
  public Phase-3 surface).
- Any sibling layer (`loopplane.scheduling`, `packs`, `review`, `recall`, `toolkit`, `governance`,
  `inspect`, `webapi`, `studio`).

## Behavioral boundary

| Rule | Enforcement | Requirement |
|---|---|---|
| Drives subagent runs **only** through `run_loop` | The package contains no loop/turn driving; it calls `run_loop` | NFR-001, NFR-002 |
| **Executes no tool** | No gateway/host import; no tool resolve/authorize/execute path | Constitution V, NFR-002, SC-005 |
| **Re-emits no live bus** | It reads each captured `LoopOutcome.events` (recorded); it passes no live sink and emits nothing | Constitution VI, NFR-003, SC-005 |
| **Aggregated views are metadata-only** | Records carry only `subagent` / `type` / `sequence` / session id + artifact reference; never a payload value or content | FR-021, FR-031, NFR-006, SC-003 |
| **Deterministic** | Registration-ordered; a determinism test repeats the aggregation | NFR-004, SC-002 |

## Audit (`test_orchestration_boundary.py`)

An AST + text audit over `src/loopplane/orchestration/*.py`, mirroring the Phase-3..12 boundary tests:

1. **Import allow-list** — every `loopplane.*` import is under `loopplane.engineering` (or
   `loopplane.orchestration`); 0 violations (NFR-001).
2. **No host / gateway / runtime-internal / sibling names** — a text scan finds no `loopplane.host` /
   `loopplane.gateway` / `loopplane.controller` / `loopplane.events` / `RuntimeController` /
   `serialize_event` / sibling-package token (NFR-002, NFR-003, SC-005).
3. **Metadata-only views** — a representative aggregated record carries only the declared metadata
   fields and no payload value (FR-021, FR-031, SC-003).
4. **Determinism** — for scripted subagents, the aggregated views are identical on repeat (NFR-004,
   SC-002).

## Public-safety scan (`PHASE13_TARGETS`)

`tests/contract/test_public_safety.py` is extended with the orchestration package targets: committed
sources, the example, and the doc contain no secret, private path, internal name, or IP (Principle VII,
NFR-006, SC-003).
