# Desktop GUI

The desktop app is a local Electron application under `apps/desktop/` that runs the agent
with **no server**: it spawns a **Python sidecar** that drives a `loopplane.host` and
speaks JSON-RPC V1 over stdio. Unit 078 replaced the reused web renderer with the shared
`@loopplane/cowork-presentation` package, so Desktop and Web render from one presentation
source without copying UI.

The app opens no network port, runs no tool itself (the Host does), and ships no secret of its
own. It does store one the user enters — see [Model provider](#model-provider).

## The gates (automated)

```sh
# Python sidecar, delivery contracts, and packaged-smoke driver contracts:
uv run pytest tests/integration/test_desktop_sidecar.py \
              tests/integration/test_desktop_packaged_smoke.py \
              tests/contract/test_desktop_delivery_gate.py

# TypeScript, from the repository root (one root lock, npm workspaces):
npm ci
npm run typecheck -w @loopplane/desktop
npm test -w @loopplane/desktop
npm run build -w @loopplane/desktop
```

`apps/desktop/.build/` holds local delivery scratch, including whole stale copies of this
workspace left by packaging runs. Vitest does not read `.gitignore`, so the Desktop Vitest
config excludes that directory explicitly; without it the runner collects those copies and
reports failures from old sources.

## Trust boundary

- The **renderer** is sandboxed with context isolation and no node integration. It receives
  a typed preload facade only; navigation is pinned to the packaged entry and permissions
  are denied by default.
- The **Electron main process** owns the sidecar child, the typed IPC surface, and the
  window lifecycle. It never forwards a raw error, a filesystem path, a rule, or a PID to
  the renderer: failures arrive as fixed public `runtime.state` diagnostics.
- The **sidecar** owns the Host. It has no live-store or gateway reach-through: every tool
  call goes through the Gateway inside the Host, and `tests/contract/test_desktop_boundary.py`
  asserts that boundary from source.
- Protocol failures use a fixed public error catalogue (`desktop.error.*`). A handler that
  raises yields `desktop.error.internal_failure` and nothing else; the routing scan in
  `tests/contract/test_desktop_public_safety_routing.py` proves marker-bearing exceptions
  and parameters never reach the wire.

## Startup

The sidecar negotiates before it composes anything expensive. It reads and answers
`initialize` from a lightweight dispatcher, then acquires the Profile Ownership Lock,
bootstraps the generation, opens SQLite, and builds the Host-backed methods. Electron
starts that handshake alongside window and renderer startup rather than after it, so a cold
packaged launch does not pay for both in sequence.

## OS profile ownership

One profile root is owned by exactly one running app. The layout under the profile root is:

```text
current-generation                       # pointer to the active generation
device-private/profile-owner.lock        # OS-level ownership lock
generations/<id>/profile.json            # portable profile record
generations/<id>/proof.json              # active-generation proof
generation-storage/<id>/checkpoints.sqlite3
```

A second launch against the same root fails closed on the lock rather than sharing state.
The active generation is validated against its proof before the Host starts.

## Model provider

Settings → **Model provider** is how the app reaches a real model: choose a provider
(Anthropic, OpenAI, Gemini, OpenRouter, or a local Ollama), enter a model id and an API key,
save, restart. Before this existed the only route was exporting
`LOOPPLANE_MODEL=<module>:<attr>` before launching Electron, and without it every prompt
answered "LoopPlane demo model: no provider is configured." That environment variable still
works and still takes precedence over nothing — an in-app setting wins, and a packaged-smoke
scenario wins over both.

**ADR 0016** records the decision, including the deliberate divergence from the position that
a LoopPlane UI does not collect provider credentials: Web is served across a network to a
principal who need not own the machine, while Desktop is a local application run by the
machine's owner with an OS keystore available.

- **Electron main owns the credential.** It encrypts with `safeStorage` (DPAPI / Keychain /
  libsecret) and refuses to store anything at all when the OS keystore is unavailable rather
  than falling back to plaintext.
- **The blob lives outside the profile root**, under `app.getPath("userData")`. Backups
  assemble from a profile whitelist (`sidecar/archive.py`), so the `"credentials"` exclusion
  `backup.describe` discloses holds by construction rather than by a rule that could drift.
  A restored profile therefore arrives without a provider, and the setting has to be entered
  again on the new machine.
- **The renderer never receives the key.** `providers.get` answers
  `{provider, modelId, hasKey, keyHint}`, where the hint is the last four characters at most,
  and save failures are a fixed enumeration so no OS text or path crosses the boundary.
- **The sidecar receives it as spawn environment, not as an RPC parameter**, so no method and
  no capability is added and the versioned stdio protocol is untouched. The sidecar drops the
  key from `os.environ` once the adapter holds it, so nothing the runtime later spawns
  inherits it.
- **Changing a provider relaunches the app.** `RuntimeConfig.model` is frozen and the sidecar
  holds the profile ownership lock, so a relaunch is the one path that rebuilds both without a
  partial teardown. A stored key is reused when only the model changes, never across a
  provider change.

Saving stores the key; it does not verify it. An incorrect key surfaces on the first reply.

## Capability management and cost (unit 083)

Settings holds nine tabs: **Model provider** (desktop-only, above), **Capabilities**
(availability cards), **Agent controls**, and — since unit 083 — **Memory**, **Skills**,
**MCP**, **Workspace**, **Schedules**, and **Model default**, rendered from the same
shared panels Web uses, each behind a narrow service port over sidecar RPC. The
conversation pane's context strip shows the session's spend once the host can price it —
`$` amounts are the host's exact `Decimal` strings, and unpriced / partially priced /
unknown / unavailable are each their own state, never `$0`. Month-to-date spend from the
durable ledger appears in Inspection.

**Per-domain availability** is reported by the `capabilities.list` cards, never by
protocol negotiation: MCP needs the host's endpoint policy, Schedules needs a configured
schedule runner, Workspace contexts need storage, Model default needs a configured
provider model, and the monthly Cost figure needs a USD ledger. An unconfigured domain
answers *unavailable with a reason*; nothing is forced on, and nothing renders as an
empty success.

**Public-safety posture.** Every projection is a field-by-field allowlist: no MCP
endpoint URL, header, token, credential, `owner_id`, raw `problem` text, or filesystem
path ever reaches the renderer. Desktop is deliberately stricter than Web here — an MCP
endpoint is write-only (it goes *in* on save and never comes back, so reopening a server
leaves the endpoint field blank). Every durable mutation acquires the profile mutation
lease under a **main-generated** mutation id (a renderer-supplied id never reaches the
sidecar) and a held lease refuses with a public busy reason rather than queueing.

### MCP browser sign-in (unit 084)

Desktop's MCP form adds an **Authorization** choice for HTTP and SSE servers: **None** or
**Browser sign-in**. WebSocket keeps the pre-existing no-interactive-auth path. Saving a
browser-sign-in server records only the mode and initially shows **Needs authorization**;
press **Connect** to open the system browser and complete the loopback callback. The card
then shows **Authorized** or **Authorization failed**. The browser wait is bounded; an
expired or abandoned attempt fails visibly and a later Connect starts a fresh flow.

The Electron main process owns the browser, callback listener, and OS `safeStorage` vault.
The vault lives under Electron's user-data directory, outside the portable profile, and
refuses persistence when OS encryption is unavailable — there is no plaintext fallback.
The renderer and sidecar's public projections see only `{server, mode, state}`. Neither
portable backup nor restore carries token material.

On restart, main restores saved material without opening a browser. Successful unattended
refresh writes rotated material back to the vault; a refresh failure stays fail-closed and
returns to **Needs authorization** instead of sending an anonymous request or waiting on an
unobserved browser handler. **Disconnect** deletes both the durable vault copy and the
sidecar's process copy while retaining the server configuration; the next Connect therefore
requires approval again. **Delete** removes the configuration as well.

**Adding a sidecar method touches six registries in one change** — miss any and either a
test or the packaged handshake fails closed: `_DESKTOP_METHOD_NAMES` in
`sidecar/bridge.py`, the two hardcoded exact-equality lists in
`tests/integration/test_desktop_sidecar.py`, and the `REQUIRED_METHODS` allowlist in
`electron/sidecar-rpc.ts` plus its two test copies (`electron/__tests__/helpers.ts`,
`src/__tests__/sidecar-rpc.test.ts`) — the client validates the handshake's announced
methods by exact membership and refuses the runtime as incompatible on any mismatch.

Two capabilities are deliberately absent pending maintainer decisions (see
`specs/083-desktop-capability-parity/plan.md`): per-session **model selection**, because
a single-adapter host cannot honor it (`ModelRequest` carries no model id — the
selection would change the label, not the model), and composer **host commands**
(`/cost`, `/model`, …), because `CommandRegistry` lives in `loopplane.commands`, outside
the sidecar boundary allow-list.

## Profiles and workspaces

Projects group sessions; workspaces are explicit user-chosen directories bound through the
system directory chooser. A workspace reference records availability, so a relinked or
missing directory degrades visibly instead of silently widening scope. The renderer never
receives a filesystem path for a workspace it did not choose in that session.

## Backup, disclosure, and recovery

`backup.describe` returns the disclosure before anything is written: the archive is
**unencrypted** and carries the portable profile, projects and safe preferences, session
checkpoints, and eligible referenced gateway artifacts. It **excludes** unsent composer
drafts and credentials — an exclusion asserted from the product path, not only documented.

`backup.create` builds one canonical ZIP, reopens and revalidates it, then publishes it
atomically. Restore is a three-step lease: `restore.validate` checks the archive without
staging into the live profile, `restore.commit` publishes a new generation, and
`restore.cancel` releases without mutating the active profile.

## Delivery (unit 078)

Producing a packaged artifact is **not** a bare tool invocation. Four scripts own it and
they are the only route:

| Script | Role | Credentials |
|--------|------|-------------|
| `scripts/verify-desktop-stage-b.ps1` | The sole tokenized authority process. Refetches the bootstrap, final, and delivery reviews, proves pairwise-distinct IDs on one pull request, reruns the full-tree allowlist, and emits a bounded non-secret descriptor. | `LOOPPLANE_STAGE_B_GITHUB_TOKEN` only, and only here |
| `scripts/build-desktop-package.ps1` | The sole complete-artifact route. Builds only from the descriptor's read-only reviewed-source and accepted-dependency snapshots. | Refuses to run if any GitHub token is present |
| `scripts/build-desktop-sidecar.ps1` | The sole freeze route. Exports a hashed production requirements snapshot and runs PyInstaller from it. | Refuses to run if any GitHub token is present |
| `scripts/smoke-desktop-artifact.ps1` | The packaged UI-Automation smoke over a copy outside the checkout. | None |

Do not install or invoke PyInstaller directly. It is a **build-only** dependency pinned in
`apps/desktop/sidecar/pyinstaller-build.in`, deliberately absent from `pyproject.toml` and
`uv.lock`, and `tests/contract/test_packaging.py` asserts that absence.

## Required Windows CI

`.github/workflows/desktop.yml` has two jobs:

- **source-gates** — runs on push and pull request over the delivery determinants: root npm
  and Python authorities, Desktop, Web, shared presentation, `src/`, `tests/`, all four
  delivery scripts, ADR 0015, and the 078 spec tree. It never freezes, packages, or smokes.
- **delivery** — runs only on a `pull_request_review` whose state is approved. It checks out
  the reviewed commit, rechecks source, runs the tokenized verifier, then removes every
  token before invoking the token-free wrappers and the external-CWD smoke.

## External-CWD package validation

The smoke refuses to run against anything inside the checkout — executable, scratch root,
evidence file, generated profile, or **working directory** — and it refuses reparse points
anywhere in those path chains.

The working-directory check reads the *process* working directory. In PowerShell,
`Push-Location` moves only the provider location and leaves the process directory alone, so
it cannot satisfy this contract: the run fails closed with `checkout_cwd_forbidden` before
any window appears. Launch the driver with an explicit working directory instead:

```powershell
$runRoot = Join-Path $env:TEMP ('loopplane-smoke-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
Copy-Item -LiteralPath <release>\win-unpacked -Destination (Join-Path $runRoot 'artifact') -Recurse

Start-Process -FilePath 'powershell.exe' -WorkingDirectory $runRoot -NoNewWindow -Wait -PassThru `
  -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', '<repo>\scripts\smoke-desktop-artifact.ps1',
    '-AppExecutable', (Join-Path $runRoot 'artifact\LoopPlane.exe'),
    '-ScratchRoot',   (Join-Path $runRoot 'smoke-scratch'),
    '-EvidencePath',  (Join-Path $runRoot 'smoke-evidence.json'),
    '-Scenario', 'all'
  )
```

### Two couplings between the smoke and the UI

Both are easy to break with an ordinary presentation change, and neither fails until a
packaged run:

1. **The word "usable".** `Wait-RuntimeUsable` matches `/usable/i` against the descendant
   accessible names of the `LoopPlane smoke runtime status` group and throws
   `runtime_not_usable` otherwise. The renderer therefore keeps the exact phase sentence as
   that element's `aria-label` while showing a short human status; `App.test.tsx` pins the
   word separately from the copy so rewording the UI cannot silently remove it.
2. **The success marker's location.** The happy path reads the descendant accessible names of
   the `LoopPlane smoke latest outcome` group until `loopplane-packaged-smoke-ok` appears.
   That group is the pane body, so the conversation has to keep rendering inside it — a
   first-run panel that replaces the message list, rather than sitting above it, passes every
   unit test and fails the smoke.

**Unverified since the composer became multi-line:** the happy path fills the prompt through
`ValuePattern.SetValue()`, and the prompt changed from `<input>` to `<textarea>`. Chromium
exposes ValuePattern on both, and `renderer-presentation.test.tsx` pins the properties that
rests on, but jsdom cannot exercise UI Automation and neither can a headless browser — Chrome
does not expose page content to a UIA client at all. **The next packaged run is the first
real check of it; look there first if the happy path fails.**

`-Scenario all` runs the happy path plus missing, corrupt, and incompatible sidecars. Each
scenario gets a fresh profile, the copied sidecar is restored byte-for-byte afterwards, and
the run fails closed on an orphan process or a local TCP listener owned by the app.

`apps/desktop/.build/`, the frozen sidecar output, the renderer `dist/`, and `release/` are
local build products. `.build/` and `dist-electron/` are untracked but **not** ignored, so
never stage them by directory.
