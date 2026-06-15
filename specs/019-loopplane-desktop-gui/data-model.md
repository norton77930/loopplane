# Phase 1 Data Model: Desktop GUI

## Bridge protocol (line-delimited JSON over stdio)

Requests (renderer → sidecar), one JSON object per line:

```
{ "op": "run", "prompt": string }
{ "op": "approval", "request_id": string, "allow": boolean }
{ "op": "question", "request_id": string, "answers": string[] }
```

Replies (sidecar → renderer), one per line:

```
<serialize_event(event)>                          # one per normalized event, verbatim
{ "op": "outcome", "reason": string, "turns": number }   # the run's terminal outcome
{ "op": "error", "detail": string }                # a public-safe error
```

The event lines are exactly the unit-011 `serialize_event` payloads, so the renderer
parses them with the same shape the 018 SSE parser uses.

## Python sidecar (`apps/desktop/sidecar/bridge.py`)

```python
async def collect_events(host: LoopPlaneHost, prompt: str) -> list[str]:
    """Drive one run; return the serialized event lines (the testable core)."""

async def serve(host, stdin, stdout) -> None:
    """Read request lines, drive runs, write event + outcome lines (the stdio loop)."""
```

`collect_events` reuses `host.run(prompt, sink)` with a sink that appends
`serialize_event(event)`; it is asserted in the Python gate with a scripted host.

## TS sidecar transport (`apps/desktop/src/sidecar.ts`)

```
interface DesktopBridge {                 // what preload exposes as window.api
  send(line: string): void;
  onLine(handler: (line: string) => void): () => void;
}

class SidecarTransport {
  constructor(bridge: DesktopBridge);
  run(prompt: string): AsyncIterable<RawEvent>;   // mirrors 018's ApiClient.streamRun
  answerApproval(requestId: string, allow: boolean): void;
  answerQuestion(requestId: string, answers: string[]): void;
}
```

`run` sends a `run` request line and yields parsed `RawEvent`s (reusing 018's types)
until the `outcome` line. Tested in Vitest against a stubbed `DesktopBridge`.

## Renderer (reuses unit 018)

`App.tsx` uses 018's `initialState` / `reduce` / `userPrompt` and the
`Conversation` / `Timeline` / `Prompts` components (via the `@web` alias), driven by
`SidecarTransport` instead of the HTTP client. No UI is copied.

## Electron shell

- `electron/main.ts`: spawns the Python sidecar (`python apps/desktop/sidecar/bridge.py`),
  creates the window, and pipes sidecar stdout lines → renderer and renderer lines →
  sidecar stdin; on window close it stops the sidecar (no orphan).
- `electron/preload.ts`: exposes `window.api` (`send` / `onLine`) over `contextBridge`.
