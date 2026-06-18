# Manual QA / acceptance checklist

The **human** pass before a release or public announcement: actually run LoopPlane
on each surface, the way a user would. This complements
[Release readiness](./release-readiness.md), which covers the **automated** gates
(build, lint, types, tests, packaging). Here you exercise the paths CI does not —
the real browser UI, the desktop window, the packaged installer, and a real model.

Tick every box for the surfaces a release touches, then record the outcome in the
[sign-off](#sign-off) table. Commands are shown in POSIX shell; on PowerShell set
env vars with `$env:NAME = "value"`.

## 0. Automated gates (run first)

The full gate set lives in [Release readiness](./release-readiness.md). Quick form:

```sh
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest && uv build
```

- [ ] **Python gate** green — includes `tests/integration/test_examples_smoke.py`, which runs every credential-free example.
- [ ] **Web JS gate** green — `cd apps/web && npm ci && npm run typecheck && npm test && npm run build`.
- [ ] **Desktop JS gate** green — `cd apps/desktop && ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm ci && npm run typecheck && npm test`.

## 1. Core runtime smoke (no keys, no network)

- [ ] `uv run python examples/host_quickstart.py` → prints a normalized event stream ending in `run-terminated`, exits 0.
- [ ] `uv run pytest tests/integration/test_examples_smoke.py` → every credential-free example exits 0.

## 2. Web app — browser (no keys)

Proves login, live streaming, and the session UI against a **real HTTP server**,
using the credential-free demo model (canned replies). For a real conversation,
point the host at a real model — see §4.

1. Start a demo web/API host on `http://localhost:8000` (the port `apps/web` proxies to). Save this as a local file (do **not** commit it) and run `uv run python serve_web_demo.py`:

   ```python
   # serve_web_demo.py — local manual-QA helper (do not commit)
   import uvicorn
   from loopplane.cli.providers import DemoModel
   from loopplane.host import LoopPlaneHost, RuntimeConfig
   from loopplane.webapi import create_app, token_authenticator

   host = LoopPlaneHost(RuntimeConfig(model=DemoModel()))
   app = create_app(host, authenticator=token_authenticator({"dev-token": "demo-user"}))
   uvicorn.run(app, host="127.0.0.1", port=8000)
   ```

2. In another terminal: `cd apps/web && npm install && npm run dev`, then open the URL Vite prints (e.g. `http://localhost:5173`).

Check:

- [ ] The **login screen** shows (no token → no chat UI).
- [ ] Enter token `dev-token` → the chat UI loads (the app sends `Authorization: Bearer dev-token`).
- [ ] Submit a prompt → assistant text **streams** in and the run reaches a normalized termination.
- [ ] The **session list** shows the session; viewing its history works.
- [ ] Reload the tab → still logged in (token in `sessionStorage`); **Log out** → returns to login.
- [ ] Enter a wrong token → a request returns **401** → the app returns to login (token cleared).

> **Windows note (localhost / IPv6).** On Windows, `localhost` usually resolves to
> IPv6 `::1` first, but the snippet above binds IPv4 `127.0.0.1`. Vite proxies `/v1`
> to `http://localhost:8000`, so the proxy then reaches `::1:8000` (nothing there) and
> the chat shows **"Disconnected — please retry."** Fix: bind the demo host to `::1` —
> change the last line to `uvicorn.run(app, host="::1", port=8000)` (or run
> `uvicorn serve_web_demo:app --host ::1 --port 8000`). On Linux/macOS, `127.0.0.1` is
> fine. If the browser itself cannot reach the dev server, open the exact URL Vite prints.

Reference: [Web frontend](./web-frontend.md).

## 3. Desktop app (Electron + Python sidecar)

**Dev launch** — needs the real Electron binary, so a normal install (do **not**
set `ELECTRON_SKIP_BINARY_DOWNLOAD` here):

```sh
cd apps/desktop
npm install
npm run dev      # builds the renderer and launches Electron; spawns sidecar/bridge.py
```

- [ ] A native window opens with the chat UI.
- [ ] Submit a prompt → the sidecar replies and the run streams.
- [ ] Close the window → the Python sidecar exits (no orphan process).

**Packaged installer** — the reserved manual/CI step ([Desktop GUI § Packaging](./desktop-gui.md)). On each target OS:

```sh
cd apps/desktop
pip install pyinstaller
npm run build:sidecar     # PyInstaller -> sidecar/dist/loopplane-sidecar*
npx vite build            # renderer -> dist/ (+ compile electron/*.ts)
npm install electron-builder
npm run dist              # electron-builder -> apps/desktop/release/<installer>
# then sign / notarize per platform
```

- [ ] An installer is produced under `apps/desktop/release/`.
- [ ] Install + launch on a machine with **no system Python** → the app runs (uses the frozen sidecar).
- [ ] (Release) the per-OS installer is **signed / notarized**.

## 4. Real-model validation (needs an API key)

Validates the path CI skips — a real provider turn. Put the key in a local `.env`
(gitignored; see [`.env.example`](../.env.example)); never commit it.

- [ ] `uv run python examples/anthropic_quickstart.py` (with `ANTHROPIC_API_KEY`) and/or `examples/openai_quickstart.py` (with `OPENAI_API_KEY`) → a real model turn completes.
- [ ] `uv run pytest tests/live` → the opt-in live adapter tests pass (they `skip` without a key).
- [ ] (Optional) point the web/desktop host at a real model via `LOOPPLANE_MODEL` and chat for real.

Reference: [Real-model validation](./real-model-validation.md), [Model providers](./model-providers.md).

## Sign-off

| Surface | Mode | Checked by | Date | Result |
|---|---|---|---|---|
| Core runtime | demo | | | |
| Web app | demo | | | |
| Web app | real model | | | |
| Desktop (dev) | demo | | | |
| Desktop (installer) | packaged | | | |
| Real model | live | | | |
