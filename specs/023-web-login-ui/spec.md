# Feature Specification: Web Frontend Login UI & Auth Flow

**Feature Branch**: `023-web-login-ui` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Gap-closure Phase C, frontend (unit 023): the web app has no way for a user to authenticate against the unit-022 per-principal backend — it sends no token, so every request is denied. Add a login screen that captures an access token, gates the app behind it, persists the token for the tab session, and logs out on demand or on an authentication failure. Frontend only; the existing 018 app and the 022 backend are reused unchanged."

## Overview

With unit 022 the web/API host now denies every unauthenticated request, but the
single-page web app (unit 018) **sends no credential** — so against the secured backend a
user sees only failures and cannot use the app. The app's API client already supports
sending a bearer token, but there is **no screen to obtain or set one**, and nothing gates
the UI on being authenticated.

This unit adds the **login experience**: a screen where the user enters their access
token, after which the app builds a token-carrying client and shows the existing chat /
session UI. The token is **persisted for the browser-tab session** (it survives a reload
within the tab and is cleared when the tab closes), so the user is not forced to re-enter
it on every reload. A **logout** control clears the token and returns to the login screen,
and an **authentication failure** (a denied API call) does the same automatically —
without leaking the token. This is **frontend only**: the backend (unit 022) and the
existing unit-018 application, components, state, and client are **reused unchanged**; the
login/auth gate is an additive wrapper. Username/password, token issuance/refresh, an
external identity provider, and roles are out of scope — the backend verifier owns
identity; this screen only captures the token.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Log in with a token and use the app (Priority: P1)

A user opens the web app and is shown a login screen. They enter their access token and
submit; they are taken into the chat / session UI and can drive a session against the
secured backend.

**Why this priority**: Without a way to supply a credential, the app is unusable against
the 022 backend; logging in is the whole point of the unit.

**Independent Test**: Render the app root with no stored token and assert only the login
screen shows; submit a token and assert the authenticated UI appears and a session can be
driven (with a stubbed network).

**Acceptance Scenarios**:

1. **Given** no stored token, **When** the app loads, **Then** only the login screen is shown (the chat/session UI is not).
2. **Given** the login screen, **When** the user submits a valid token, **Then** the authenticated app appears and its API calls carry the token.
3. **Given** the authenticated app, **When** the user sends a prompt, **Then** the session is driven as in unit 018 (now authorized).

### User Story 2 - Stay logged in across a reload; log out on demand (Priority: P2)

The token persists for the browser-tab session, so a reload keeps the user in the app;
a logout control clears it and returns to the login screen.

**Why this priority**: Re-entering the token on every reload is poor UX; a clear logout is
expected. Both depend on token persistence being handled correctly.

**Independent Test**: With a token already stored for the tab, render the root and assert
the authenticated app shows (not login); trigger logout and assert the login screen shows
and the stored token is cleared.

**Acceptance Scenarios**:

1. **Given** a token stored for the tab session, **When** the app loads (a reload), **Then** the authenticated app shows without re-login.
2. **Given** the authenticated app, **When** the user logs out, **Then** the login screen shows and the stored token is cleared.

### User Story 3 - An authentication failure returns to login without leaking (Priority: P3)

If an API call is rejected as unauthorized (an invalid or no-longer-accepted token), the
app clears the token and returns the user to the login screen, leaking neither the token
nor internal detail.

**Why this priority**: A stale/invalid token must not strand the user in a broken app, and
the failure path must stay public-safe (Constitution VII).

**Independent Test**: Drive the authenticated app with a stubbed client that returns an
authorization failure and assert the app falls back to the login screen with no token in
the output.

**Acceptance Scenarios**:

1. **Given** the authenticated app, **When** an API call returns an authorization failure, **Then** the app clears the token and shows the login screen.
2. **Given** that fallback, **When** the screen and any error text are inspected, **Then** the token does not appear anywhere.

### Edge Cases

- **No token (first visit or after clearing)** → only the login screen; no authenticated UI.
- **Empty token submitted** → not accepted; the user stays on the login screen.
- **Reload with a stored token** → the authenticated app shows, no re-login.
- **Authorization failure mid-session** → the app returns to login; the in-progress UI is dismissed.
- **Token confidentiality** → the token never appears in the URL, in logs, or in committed code; only the user enters it.
- **Logout** → clears both the in-memory and the persisted token.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When no token is present, the app MUST show **only the login screen** and MUST NOT expose the authenticated UI.
- **FR-002**: The login screen MUST let the user enter an access token and submit it; an **empty token MUST NOT be accepted**.
- **FR-003**: On submit, the token MUST be used as the **bearer credential** for all subsequent API calls (via the existing client auth seam).
- **FR-004**: With a token present, the app MUST show the **authenticated application** (the existing chat/session UI) wired to send the token.
- **FR-005**: The token MUST **persist for the browser-tab session** — it survives a page reload within the same tab and is **cleared when the tab closes**.
- **FR-006**: A **logout** control MUST clear the token (in-memory and persisted) and return the user to the login screen.
- **FR-007**: An **API authorization failure** MUST clear the token and return the user to the login screen, **without leaking** the token or internal detail.
- **FR-008**: The token MUST NOT be **logged, placed in the URL, or embedded in committed code**; only the user supplies it (Constitution VII).
- **FR-009**: The change MUST be **frontend-only and additive** — no backend change; the existing application component and its tests are reused and **unaffected** (it still accepts an injected client).
- **FR-010**: The feature MUST be covered by **integration tests** (login flow, logout, authorization-failure-to-login) with a stubbed network; the web build / typecheck / test gate stays green and the Python suite is unchanged.

### Key Entities

- **Access token**: the user-supplied bearer credential that authorizes API calls; held in memory and persisted for the browser-tab session.
- **Frontend auth state**: the presence/absence of a token that gates the app between the login screen and the authenticated UI.
- **Login screen**: the token-entry view.
- **Authenticated app**: the existing chat/session UI, wired with a token-carrying client.

### Out of Scope

- Username/password login, token issuance / refresh / rotation, an external identity provider, and roles/permissions — the backend verifier (unit 022) owns identity; this screen only captures a token.
- The backend authentication/scoping (unit 022) and concurrent multi-user execution.
- Persisting the token beyond the browser-tab session (e.g., across browser restarts).
- A real-browser automated end-to-end suite — integration tests via the existing toolchain; a real-browser run is a manual smoke.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with a valid token logs in and can drive a session over the secured backend.
- **SC-002**: Without a token, the user sees **only the login screen** and cannot reach the authenticated UI.
- **SC-003**: A reload within the tab keeps the user logged in; **logout** returns to the login screen and clears the token.
- **SC-004**: An invalid token / authorization failure returns the user to login with **no token leak**.
- **SC-005**: The web gate (typecheck + tests + build) is green and the Python suite is unchanged.

## Assumptions

- **Token-based login (no passwords)**: the backend (unit 022) verifies a bearer token → principal; this screen only captures the token.
- **Tab-session persistence**: the token survives a reload within the tab and is cleared on tab close (the confirmed `sessionStorage` decision).
- **Integration tests + manual browser smoke**: integration tests via the existing frontend toolchain are the gate; a real-browser run is manual (the confirmed decision; consistent with unit 019's launch smoke).
- **Reuse, not rewrite**: the existing unit-018 app, components, state, and client are reused; only a login/auth wrapper and a login screen are added.
- **Additive, reversible**: removing the wrapper and the login screen restores the unauthenticated app (Constitution X rollback).
