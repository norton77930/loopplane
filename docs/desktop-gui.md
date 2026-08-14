# Desktop GUI

The desktop app is a local Electron application under `apps/desktop/` that runs the agent
with **no server**: it spawns a **Python sidecar** that drives a `loopplane.host` and
speaks JSON-RPC V1 over stdio. Unit 078 replaced the reused web renderer with the shared
`@loopplane/cowork-presentation` package, so Desktop and Web render from one presentation
source without copying UI.

The app opens no network port, runs no tool itself (the Host does), and embeds no secret.

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

`-Scenario all` runs the happy path plus missing, corrupt, and incompatible sidecars. Each
scenario gets a fresh profile, the copied sidecar is restored byte-for-byte afterwards, and
the run fails closed on an orphan process or a local TCP listener owned by the app.

`apps/desktop/.build/`, the frozen sidecar output, the renderer `dist/`, and `release/` are
local build products. `.build/` and `dist-electron/` are untracked but **not** ignored, so
never stage them by directory.
