# Phase 0 Research: Desktop GUI

Grounded in units 011/012/018; the shell is written fresh, the UI reused.

## R1 — The serverless bridge reuses the webapi's streaming shape

The unit-011 web host streams a run by driving `host.run(prompt, sink)` and sending
each event as `serialize_event(event)` (an SSE frame). **Decision**: the desktop
**sidecar bridge** does the same but frames each event as **NDJSON over stdio** (one
JSON object per line), with no HTTP server and no port (FR-001/SC-001). The bridge's
testable core is `collect_events(host, prompt) -> list[str]` (the serialized event
lines, reusing `loopplane.events.serialize_event`), so it is covered by the Python
gate with a scripted host.

## R2 — The 012 studio sidecar contract

Unit 012 defines the `SidecarHost` lifecycle (`start`/`stop`/`run`) with an in-process
implementation; its `run` returns a metadata view (its event path is a discard sink).
**Decision**: the desktop reuses the **lifecycle posture** of unit 012 (start a local
host, stop cleanly with no orphan — FR-008/SC-005) but, because the UI needs the
**event stream**, the bridge drives `host.run(prompt, on_event=…)` directly (the
streaming seam unit 011 uses), not the studio's discard-sink `run`.

## R3 — The stdio NDJSON protocol

**Decision**: a request is one JSON line `{"op":"run","prompt":"…"}`; the bridge
replies with one line per normalized event (`serialize_event`) followed by a final
`{"op":"outcome","reason":…,"turns":…}` line. Approval/question answers are request
lines (`{"op":"approval","request_id":…,"allow":…}`). The renderer transport speaks the
same protocol over Electron IPC. The protocol is line-delimited so partial reads
re-assemble deterministically (mirrors the 018 SSE parser).

## R4 — Reusing the unit-018 UI (no copy)

**Decision**: `apps/desktop` reuses 018's `RawEvent` types, the pure `reduce`, and the
components via a `@web` TypeScript path alias (`apps/web/src`). The desktop's `App.tsx`
is the same view model over a different transport — the **sidecar transport**
(`window.api`) instead of 018's HTTP `ApiClient`. No UI is copied (Constitution VII,
FR-003); the only new renderer code is the transport.

## R5 — Testing split (Python gate / JS gate / manual smoke)

**Decision**:
- The **Python bridge** is tested in the existing `pytest` gate — `tests/` loads
  `apps/desktop/sidecar/bridge.py` by file path (so it is neither in the wheel nor a
  new `loopplane` package) and asserts the event frames for a scripted run.
- The **TS transport** is tested in Vitest against a stubbed `window.api`.
- The **Electron main/preload** glue is typechecked (`tsc --noEmit`); the GUI launch is
  a **manual smoke** (consistent with unit 001's manual real-model validation), and
  `ELECTRON_SKIP_BINARY_DOWNLOAD=1` keeps the JS gate binary-free.

## R6 — Isolation + reserved packaging

**Decision**: `apps/desktop/` has its own toolchain; `node_modules`/build output are
gitignored and excluded from the Python wheel (hatch targets `src/loopplane` only).
The Python package, the web API (011), unit 012, and unit 018 are **unchanged** —
the desktop composes them. Packaging a signed, distributable installer
(electron-builder, code signing, auto-update) is **out of scope** and reserved for a
maintainer (FR-010, board release-readiness reserved extension points).
