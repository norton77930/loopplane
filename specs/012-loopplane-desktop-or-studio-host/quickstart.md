# Quickstart: Desktop / Studio Host

Validate that `loopplane.studio` presents the embedded host to a local developer — run, session
manager, interactive session, inspection, and the sidecar — **in-process, offline**, no GUI / network /
process spawn.

## Prerequisites

- The repo installed editable. **No extra dependency** — the studio is pure Python over the host +
  `anyio` (a core dep).
- A public-safe **fake model** (as in prior units' examples) so runs are deterministic and offline.

## What it provides

See [contracts/studio-api.md](./contracts/studio-api.md). Core entry point:

```text
from loopplane.studio import StudioHost
async with StudioHost(host) as studio:   # host: a LoopPlaneHost
    result = await studio.run("...")
```

## Validation scenarios

Each maps to a user story and its success criteria; all run in-process under `pytest.mark.anyio`.

### US1 — Run from the console (SC-001)
1. Build a host with a fake model; `async with StudioHost(host) as studio`.
2. `await studio.run("...")` → a `RunResultView`: a `session_id`, a public-safe `termination_reason`,
   an integer `turns_taken`, and a metadata-only `history` of `{role, block_count}` — **no** block
   text. A second concurrent run → `ErrorView(kind="conflict")`; an empty prompt → `ErrorView(invalid)`.

### US2 — Session manager
1. `await studio.open_session()` → a `session_id`; `studio.list_sessions()` includes it.
2. `studio.select(unknown)` → `ErrorView(not-found)`; `await studio.cancel(session_id)` closes it and
   frees the host.

### US3 — Interactive session (in-process)
1. Open a session with an injected `on_approval` (or answer out-of-band); `await studio.submit(id,
   prompt)` that triggers an approval → the approval is answered and the run reaches its outcome view.
2. `await studio.cancel(id)` never hangs, even when parked on an approval.

### US4 — Inspect (SC-003)
1. After a run, `studio.history_view(id)` → `HistoryEntryView`s — assert **no** block text in any view.
2. `studio.list_sessions()` → public-safe summaries; an unknown id → `ErrorView(not-found)`.

### US5 — Sidecar lifecycle (SC-006)
1. `InProcessSidecar(host)`; `await sidecar.start()`; `await sidecar.studio.run("...")` works.
2. `await sidecar.stop()` then `await sidecar.stop()` again → idempotent, no orphan; a command after
   stop → `ErrorView(kind="not-available")`.

## Boundary & public-safety (SC-005)

- `tests/contract/test_studio_boundary.py`: `loopplane.studio` imports only `loopplane.host` / `anyio` /
  stdlib; executes no tool; re-emits no live bus; views are metadata-only; no process spawn / network.
- `tests/contract/test_public_safety.py` (`PHASE12_TARGETS`): committed sources, the example, and the
  doc carry no secret / private path / internal name / IP.

## Example

[`examples/studio_quickstart.py`](../../examples/studio_quickstart.py) builds a host with a fake model,
opens a `StudioHost`, drives a run, and lists/inspects sessions — printing public-safe view models only.

## Expected outcome

All US1–US5 scenarios pass in-process with no network/GUI/process; views are metadata-only; the
interactive round-trip and the sidecar lifecycle are fail-safe. The full suite stays green and
ruff + mypy(strict) clean.
