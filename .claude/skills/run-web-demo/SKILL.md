---
name: run-web-demo
description: Launch and visually inspect the LoopPlane web UI (apps/web) against a local credential-free demo host — for manual/visual QA of the SPA (shell, theme, i18n, empty state, message actions, inspection panels).
---

# Run the LoopPlane web demo

Launch `apps/web` against a local, credential-free demo backend and drive it with a browser to
**see the UI** (units 025–032). Verified to load the styled SPA, log in, and render the chrome +
empty state + per-message actions + inspection panels. **Known caveat:** a *live streamed
conversation* disconnects on this Windows box — see "Known issue" below; the UI itself renders.

## 1. Prerequisites

- Python deps installed (`uv`), web deps installed (`npm --prefix apps/web install`).
- Build the SPA (rebuild after any UI change):
  ```sh
  npm --prefix apps/web run build
  ```

## 2. The demo backend (serves API + the built SPA, same origin)

`serve_web_demo.py` is a **gitignored** local helper (do NOT commit). Ensure it contains the
**same-origin** variant below — it serves the built SPA from `apps/web/dist` *and* the `/v1` API
from one origin, so the browser needs no Vite dev proxy:

```python
# serve_web_demo.py — local manual-QA helper (do NOT commit; gitignored).
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

from loopplane.cli.providers import DemoModel
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.webapi import create_app, token_authenticator

host = LoopPlaneHost(RuntimeConfig(model=DemoModel()))
app = create_app(host, authenticator=token_authenticator({"dev-token": "demo-user"}))

# /v1 routes are registered above, so they take precedence over this catch-all static mount.
_dist = Path(__file__).parent / "apps" / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

Run it (background) and confirm `Uvicorn running on http://127.0.0.1:8000`:

```sh
uv run python serve_web_demo.py
```

Login token: **`dev-token`**.

> *Alternative (live-reload, but flakier):* `npm --prefix apps/web run dev` (Vite, prints a port
> like `:5176`) which proxies `/v1` to `localhost:8000`. On Windows the dev proxy resolves
> `localhost` to `::1`/`127.0.0.1` inconsistently and mishandles the long-lived SSE stream — prefer
> the same-origin build above for QA.

## 3. Drive it (Playwright MCP) and LOOK

Navigate **directly** to the backend origin (no proxy), then log in and inspect:

1. `browser_navigate` → `http://127.0.0.1:8000`
2. `browser_type` the token `dev-token` into the "access token" field, submit.
3. **Take a screenshot and look at it** — a blank frame is a failure to launch. Verify:
   - the **two-pane shell** (sessions sidebar + chat column), styled (not unstyled black-on-white);
   - the **empty state**: "Start a conversation" + example-prompt chips (unit 032);
   - the **header**: status dot, Inspect toggle, language switcher (`English` / `繁體中文`), theme toggle;
   - toggling **theme** (light/dark) and **language** updates the chrome live;
   - clicking **Inspect** opens the read-only Skills/Tools/MCP/Memory panels (unit 027; these are
     plain `GET /v1/inspect/*` and work);
   - typing a message shows it with a per-message **Copy** action (unit 031).

## 4. Verify (what "working" means here)

- The styled SPA loads and login succeeds (the chat UI replaces the login card).
- Empty state + example prompts render; theme + language toggles work; the Inspect panel populates.
- REST sanity (optional, from the page console): `fetch('/v1/models', {headers:{authorization:'Bearer dev-token'}})` → `200 []`.

## Known issue — live streamed conversation disconnects (Windows, local)

Submitting a prompt renders the user message + a **Copy** action and then the status flips to
**Disconnected** with a **Retry** banner (unit 032, behaving correctly). Diagnosis gathered:
- It is **not** the Vite proxy (same-origin reproduces it) and **not** a 025–032 code defect — the
  Python suite (767) + `apps/web` Vitest (101) are green, and plain `/v1` REST calls return 200.
- The app's interactive **session / SSE** flow (`POST /v1/sessions` → `GET /v1/sessions/{id}/events`
  → `submit`) does not complete here; it is an environment-level live-SSE issue on this box
  (related to the in-process-SSE note in project memory).

To get a fully streamed conversation: try **WSL/Linux**, or run **`/run-skill-generator`** (a
user-only command) to cold-start in a clean environment and capture a verified end-to-end recipe.

## Cleanup

Stop the backend (and the Vite dev server if used); close the browser. Do **not** commit
`serve_web_demo.py` or any screenshots.
