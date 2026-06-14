# Quickstart: The Web Frontend

The UI lives under `apps/web/` with its own toolchain, isolated from the Python package.

## Develop

```sh
cd apps/web
npm install
npm run dev        # Vite dev server, proxying /v1 to a running web API host
```

Point it at a running unit-011 web/API host (e.g. `examples/webapi_quickstart.py`).

## Test and build (the JS gate)

```sh
cd apps/web
npm run typecheck  # tsc --noEmit
npm test           # vitest run — the pure core (events / reducer / client) + component smoke tests
npm run build      # vite build -> static assets in apps/web/dist
```

These run in CI via `.github/workflows/web.yml`, separate from the Python gate.

## Shape

- `src/api/client.ts` — the `/v1` REST + SSE client (fetch-injectable, auth at runtime).
- `src/api/events.ts` — SSE frame → normalized event parsing.
- `src/state/chat.ts` — a pure reducer folding events into the conversation + timeline.
- `src/components/*` — thin React views over that state (Conversation, Timeline,
  Prompts, SessionList).

The deterministic core is covered by Vitest with a stubbed `fetch` and canned event
frames — no server, no credentials. The UI renders only metadata-safe content and
embeds no secret.
