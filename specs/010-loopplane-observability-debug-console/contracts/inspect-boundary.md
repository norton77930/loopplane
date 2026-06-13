# Contract: Read-Only / Metadata-Only Boundary

The inspect layer transforms **recorded** event streams into inspection value structures; it never drives a
run, never re-emits the live buses, and reads only metadata (Constitution VI).

## Integration

```python
# A host captures the recorded streams (e.g., via the Phase-3 LoopEventSink / Phase-1 EventSink) and hands
# them to the inspect transforms after the fact:
diagnostics = loop_diagnostics(recorded_loop_events)
trace = build_trace(recorded_loop_events, {session_id: recorded_run_events})
```

- The layer **consumes** recorded streams and returns value structures; capturing the streams is the host's
  concern (the Phase-1/Phase-3 sinks). The layer drives nothing.

## Boundary (FR-061, NFR-003, NFR-006)

```text
loopplane.inspect  ──imports──►  loopplane.engineering  (LoopEvent, LoopEventType, reconstruct_state,
                                                         LoopState, LoopOutcome)
                   ──imports──►  loopplane.events       (RuntimeEvent + typed events, TerminationReason)
                   ──imports──►  (stdlib only otherwise)
```

Prohibited (asserted by the import + no-run audit, `test_inspect_boundary.py`):

- The layer **drives no run** and **re-emits no live-bus event**: the audit asserts no `run_loop` /
  `LoopController` / host / `.run(` reference and no live-bus emission (FR-002, FR-061, NFR-006).
- It reads **only metadata**: a metadata-only test asserts produced artifacts carry no content, tool
  arguments, or outputs (FR-001, FR-060).
- It imports **no** Phase-1/Phase-3 runtime control internal (`loopplane.controller`, `loopplane.host`,
  `loopplane.gateway`, `loopplane.context`) and **no** sibling layer (`scheduling`, `packs`, `review`,
  `recall`, `toolkit`, `governance`) (FR-061, NFR-003).

Allowed `loopplane.*` import prefixes: `loopplane.engineering`, `loopplane.events`, `loopplane.inspect`.
Everything else is a boundary violation.

## Non-duplication (FR-062, SC-008)

The layer contains no run/loop driving, no event serialization, and no state-reconstruction logic. Loop
diagnostics reuse `reconstruct_state`; the live buses stay the Phase-1/Phase-3 surfaces'; it only consumes
recorded streams.
