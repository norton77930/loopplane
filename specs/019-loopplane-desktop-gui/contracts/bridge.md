# Contract: The Sidecar Bridge

The serverless, local transport between the desktop renderer and a `loopplane.host`.

## Protocol (line-delimited JSON over stdio)

Request lines (renderer → sidecar):

| Line | Effect |
|---|---|
| `{"op":"run","prompt":S}` | drive one run; stream its events back |
| `{"op":"approval","request_id":R,"allow":B}` | answer a pending approval |
| `{"op":"question","request_id":R,"answers":[S…]}` | answer a pending question |

Reply lines (sidecar → renderer):

| Line | Meaning |
|---|---|
| `serialize_event(event)` | one normalized event, verbatim (the unit-011 serialization) |
| `{"op":"outcome","reason":S,"turns":N}` | the run's terminal outcome |
| `{"op":"error","detail":S}` | a public-safe error (e.g. a run already active) |

No HTTP server is opened and no port is bound (FR-001/SC-001).

## Python sidecar (`apps/desktop/sidecar/bridge.py`)

- `collect_events(host, prompt)` drives `host.run(prompt, sink)` where `sink` appends
  `serialize_event(event)`; it returns the event lines (the testable core).
- `serve(host, in, out)` runs the stdio loop. It runs **no tool** itself and re-emits
  no bus — it is a streaming consumer of the normalized stream (V/VI).
- Reuses only `loopplane.host` + `loopplane.events.serialize_event`; adds no new
  dependency and is not added to the wheel (loaded by path in tests).

## TS transport (`apps/desktop/src/sidecar.ts`)

`SidecarTransport.run(prompt)` sends a `run` line over `window.api` and yields parsed
`RawEvent`s (reusing 018's types) until the `outcome` line; `answerApproval` /
`answerQuestion` send their request lines. A dropped bridge surfaces a typed error the
UI renders as a clear state (FR-008). Tested in Vitest with a stubbed bridge.

## Guarantees

- Serverless: the bridge opens no network listener.
- The renderer runs no tool; the host does (V); the renderer only renders events (VI).
- Metadata-only, public-safe: the lines carry the same metadata-safe content the web
  API exposes; no secret is embedded in the app (VII).
