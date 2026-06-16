# Feature Specification: Desktop Packaging

**Feature Branch**: `024-desktop-packaging` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Gap-closure Phase D, the final unit (024): the desktop app (unit 019) spawns the Python sidecar via system `python` and has no packaging, so it cannot be distributed to an end-user without Python. Ship Python by freezing the sidecar into a standalone executable, add packaging that bundles it into an installer, and have the app spawn the frozen sidecar in a packaged build (falling back to system Python in development). Deliver the packaging pipeline + offline tests + docs; the actual signed installer build is a reserved manual/CI step. Desktop app only."

## Overview

The desktop app (unit 019) is an Electron shell that, at runtime, **spawns the Python
sidecar with the system `python`** and assumes `loopplane` is importable there — and it
has **no packaging** (no installer build). So while it runs on a developer's machine, it
**cannot be distributed to a normal end-user** who has no Python (the app would launch but
the sidecar would fail to start).

This unit makes the desktop app a **distributable product** by shipping Python **frozen**:
a freeze step bundles the sidecar bridge together with `loopplane` into a **standalone
sidecar executable** that runs with **no system Python**; a packaging configuration bundles
the Electron app, the built renderer (the unit-018 UI), and that frozen sidecar into an
**installer**; and the Electron main process **spawns the bundled frozen sidecar** in a
packaged app, **falling back to system `python` + the bridge script in development** so the
existing dev flow is unchanged. This is **desktop-app only** — the runtime package, the
hosts, the web UI, the sidecar bridge, the transport, and the preload are **reused
unchanged**. Consistent with unit 019 (whose GUI launch is a manual smoke and whose signed
installer was reserved), this unit delivers the **packaging pipeline** — the config, the
freeze specification, the spawn resolver, offline tests, and docs — while **producing and
signing the actual per-OS installer remains a reserved manual / CI step**. The freeze tool
is **PyInstaller** and the packager is **electron-builder**; the CLI (a pip-installed
Python package) and the web frontend (static assets + a separately-run Python host) are
distributed differently and are unaffected.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the packaged app without a system Python (Priority: P1)

An end-user installs the desktop app and launches it; it drives the agent **without** the
user having Python or `loopplane` installed, because the sidecar is a frozen, bundled
executable the app spawns.

**Why this priority**: Being usable by someone who has no Python is the entire point of
packaging — it turns the desktop app from a developer toy into a distributable product.

**Independent Test**: Offline — the spawn resolver, in "packaged" mode, targets the
**bundled frozen sidecar executable** (not system `python`), and the packaging config
bundles exactly that executable (unit-tested + a config/spec consistency check). The full
end-to-end "runs with no Python" is the reserved manual / CI smoke.

**Acceptance Scenarios**:

1. **Given** a packaged app, **When** the main process starts the sidecar, **Then** the resolver targets the bundled frozen sidecar executable, not system `python`.
2. **Given** the packaging configuration, **When** it is inspected, **Then** it bundles the frozen sidecar the freeze specification produces (a path/name both agree on).

### User Story 2 - Development still works unchanged (Priority: P2)

A developer runs the app in development and it spawns `python` + the bridge script exactly
as before — the packaging change does not disturb the dev loop.

**Why this priority**: The additive change must not regress the existing unit-019
development experience; a developer keeps iterating without building a frozen binary.

**Independent Test**: Offline — the spawn resolver, in development mode, targets system
`python` + the bridge script; the existing unit-019 behavior is unchanged.

**Acceptance Scenarios**:

1. **Given** development mode (no packaged binary), **When** the main process starts the sidecar, **Then** the resolver targets system `python` + the bridge script.
2. **Given** the existing unit-019 app and tests, **When** they run, **Then** they pass unchanged.

### User Story 3 - A maintainer can build the installer from a documented procedure (Priority: P3)

A maintainer follows a documented procedure to freeze the sidecar and build the installer;
the config and the freeze specification are consistent, so the build wires together.

**Why this priority**: The pipeline must be runnable by the maintainer/CI even though the
heavy build is not in the default gate; consistency between the freeze and the package is
what makes the documented build succeed.

**Independent Test**: Offline — the freeze specification and the packaging config exist and
reference each other consistently (asserted by a test / documented check); the actual build
is the reserved manual / CI step.

**Acceptance Scenarios**:

1. **Given** the freeze specification and the packaging config, **When** they are checked, **Then** they are mutually consistent (the config bundles the frozen executable the spec names).
2. **Given** the documentation, **When** a maintainer follows it, **Then** the steps to freeze, package, and (reserved) sign are clear.

### Edge Cases

- **Packaged app** → spawn the bundled frozen sidecar executable.
- **Development (no frozen binary)** → spawn system `python` + the bridge script.
- **Per-platform executable name** (e.g. a `.exe` suffix) → handled by the resolver.
- **Frozen sidecar missing in a packaged app** → a clear surfaced failure, not a silent hang.
- **Built artifacts** (frozen sidecar, installer, renderer build output) → gitignored, never committed.
- **Unsigned build** → the OS may warn about an unidentified developer; documented, since signing/notarization is reserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The desktop app MUST be **packageable into a distributable installer** that bundles the app, the built renderer, and a **frozen Python sidecar executable**.
- **FR-002**: A **packaging configuration** MUST exist that produces the installer and includes the frozen sidecar as a bundled resource.
- **FR-003**: A **freeze specification** MUST exist that bundles the sidecar bridge together with the runtime package into a **standalone executable that runs without a system Python**.
- **FR-004**: In a **packaged** app, the main process MUST spawn the **bundled frozen sidecar executable** (not system Python).
- **FR-005**: In **development**, the main process MUST fall back to spawning **system `python` + the bridge script**, so the existing development flow is unchanged.
- **FR-006**: The packaged-vs-development selection and the per-platform executable name MUST be a small, deterministic, **unit-testable resolver**.
- **FR-007**: The freeze specification and the packaging configuration MUST be **mutually consistent** — the config bundles exactly the frozen executable the spec produces (a path/name both agree on).
- **FR-008**: A **missing** frozen sidecar in a packaged app MUST **fail clearly** (a surfaced error), not hang silently.
- **FR-009**: The change MUST be **desktop-app only** — no change to the runtime package, the hosts, the web UI, the sidecar bridge, the transport, or the preload; the existing unit-019 app and tests are reused and **unaffected**.
- **FR-010**: Built artifacts (the frozen sidecar, the installer, the renderer build output) MUST be **gitignored and never committed**; no secret or credential is committed.
- **FR-011**: The desktop test/typecheck gate MUST stay green and the runtime (Python) suite MUST be unchanged. Producing/signing the actual per-OS installer is a **reserved manual / CI step**, not part of the default gate.
- **FR-012**: A **documented build procedure** MUST describe how to freeze the sidecar, build the installer, and what ships (including the reserved signing step).

### Key Entities

- **Frozen sidecar executable**: the standalone, Python-free bundle of the sidecar bridge + the runtime package; the app spawns it in a packaged build.
- **Packaging configuration**: the configuration that produces the installer and bundles the app + renderer + frozen sidecar.
- **Freeze specification**: the description of how the sidecar bridge + runtime are frozen into the standalone executable.
- **Sidecar spawn resolver**: the deterministic, per-platform selection of which executable to spawn — the packaged frozen binary, or system `python` + the bridge in development.

### Out of Scope

- **Producing, signing, or notarizing** the actual per-OS installers — a reserved manual / CI step.
- Running the cross-platform freeze / installer build in the **default gate**.
- Auto-update and app-store distribution.
- Any change to how the **CLI** (a pip-installed Python package) or the **web frontend**
  (static assets + a separately-run Python host) are distributed — they are unaffected.
- Multi-user / concurrency — the desktop app is a single local user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The packaging configuration and the freeze specification exist and are **mutually consistent** (the config bundles the frozen executable the spec names).
- **SC-002**: The main process spawns the **frozen sidecar in a packaged app** and **system Python + the bridge in development** — verified by a unit test of the resolver.
- **SC-003**: The desktop gate (typecheck + tests) is **green** and the runtime (Python) suite is **unchanged**.
- **SC-004**: A **documented build procedure** produces a desktop app that runs with **no system Python** (verified manually / in CI, not in the default gate).
- **SC-005**: **No built artifact or secret is committed** (gitignored; a clean scan).

## Assumptions

- **Frozen Python (PyInstaller)**: the sidecar ships as a standalone frozen executable, so end-users need no system Python (the confirmed decision).
- **Pipeline + offline tests scope**: this unit delivers the packaging configuration, the freeze specification, the spawn resolver, offline tests, and docs; the actual signed per-OS installer is a **reserved manual / CI step** (the confirmed decision; consistent with unit 019).
- **Per-OS build**: the freeze and installer are produced per platform by the maintainer / CI; the local environment may not reproduce a full signed installer.
- **Reuse, not rewrite**: the unit-019 app, the sidecar bridge, the transport, the preload, and their tests are reused unchanged; only the packaging config, the freeze spec, the spawn resolver, and docs are added.
- **Additive, reversible**: removing the packaging config / freeze spec and the resolver's packaged branch restores the development-only app (Constitution X rollback).
