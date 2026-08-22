# Tasks: MCP Interactive OAuth

**Input**: Design documents from `specs/084-mcp-interactive-oauth/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/mcp-interactive-oauth.md),
[ADR 0019](../../docs/adr/0019-mcp-interactive-oauth.md)

**Tests**: required (Constitution X). Every phase below carries its own tests; three of this unit's
requirements are negatives and get constructive guards plus a negative self-check.

## 🚦 Gate — nothing below may start yet

- [x] **T000** **ADR 0019 accepted by the maintainer** on 2026-08-22, before implementation began
      (spec FR-017; R2 credential trigger). The ADR status line reads `Accepted`. Gate discharged.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency
- **[Story]**: the user story from spec.md the task serves

---

## Phase 1: Runtime seams (Foundational — blocks every story)

**Purpose**: the two Protocols, the in-memory default, and the configuration mode. Nothing in later
phases can be written before these exist.

- [x] **T001** [US1] Create `src/loopplane/adapters/mcp/oauth.py` with the `McpAuthorizationHandler`
      and `McpTokenStore` Protocols per [data-model.md](data-model.md). Types only, no behaviour.
- [x] **T002** [US1] Add `InMemoryMcpTokenStore` to the same module — the **only** implementation
      this unit ships (C4.1): `(principal, server)`-keyed, process-lifetime, **no `repr`/`str` that
      can surface material** (C6.3).
- [x] **T003** [P] [US1] Focused RED — `tests/unit/test_mcp_oauth.py`: the in-memory store isolates by
      principal and by server, discard is idempotent and reveals nothing (C4.3, C4.4).
- [x] **T004** [US1] Add the `authorization` mode to `MCPServerConfig`
      (`src/loopplane/adapters/mcp/config.py`) and extend `_check_transport_fields`: mutually
      exclusive with `auth_token`; rejected on `stdio` and `websocket` (C3.2, C3.4).
- [x] **T005** [P] [US1] Focused RED — invalid combinations disable **only the offending entry**
      through the existing `merge_layers` path, leaving other servers and a broader-layer definition
      intact (C3.5).
- [x] **T006** [US1] Export the Protocols and the default store from
      `src/loopplane/adapters/mcp/__init__.py`.
- [x] **T058** [P] [US1] Test — **default-unused is byte-identical** (C10.1, FR-016): a configuration
      declaring no mode behaves exactly as the current release, the ADR 0007 static-token path
      included. *Added at analyze — the property was asserted in a checkpoint but had no task.*
- [x] **T059** [P] [US1] Test — **`websocket` is untouched** (C3.3): no `auth`, no headers, behaviour
      identical to today, so ADR 0007 D3's limitation is preserved rather than silently altered.
      *Added at analyze.*

**Checkpoint**: the seams exist and are unused. The full suite must still pass unchanged (C10.1).

---

## Phase 2: US1 — First-time authorization (P1)

- [x] **T007** [US1] In `oauth.py`, compose the SDK's `OAuthClientProvider` (C1.1, C1.2, C2.1):
      bridge the host handler to `redirect_handler` / `callback_handler` and the host store to
      `TokenStorage`.
- [x] **T008** [US1] Add constant-time `state` validation and single-consumption of an authorization
      result; enforce the authorization timeout (C2.2–C2.5).
- [x] **T009** [US1] In `adapter.py`, accept the two seams as constructor parameters (ADR 0019 D2 —
      **not** a `RuntimeConfig` knob) and pass `auth=` alongside the existing `headers=` on the
      `http` and `sse` branches only (C3.1).
- [x] **T010** [P] [US1] Test — a stubbed flow registers the server's tools with the same descriptors
      and qualified names as an unauthenticated server (C1.4).
- [x] **T011** [P] [US1] Test — mismatched, missing, and replayed `state` each fail the connection
      with no automatic retry (C2.3, C2.4).
- [x] **T012** [P] [US1] Test — authorization timeout leaves the server unconnected and discards the
      pending flow (C2.5).

**Checkpoint**: an offline stubbed flow authorizes and registers tools. US1 is independently
demonstrable.

---

## Phase 3: US3 + US2 — Fail closed, then renew unattended (P1)

Ordered fail-closed first: the safety property must exist before the convenience property.

- [x] **T013** [US3] With no authorization handler configured, a server declaring the mode does not
      connect and makes **no** unauthenticated attempt (C5.4).
- [x] **T014** [US3] Contain every authorization failure to its own server; other servers connect and
      keep their tools (C5.5), reusing the existing per-server isolation rather than adding a path.
- [x] **T015** [P] [US3] Test — an interactive server with no handler, alongside a healthy server:
      zero connections for the first, full tool set for the second.
- [x] **T016** [US2] Renewal from valid refresh material, **without** invoking the authorization
      handler (C5.1).
- [x] **T017** [US2] Failed renewal disconnects and reports re-authorization needed; **no**
      unauthenticated retry and **no** fallback to the 059 static token (C5.2, C5.3).
- [x] **T018** [P] [US2] Test — renewal path asserts the handler invocation count is exactly zero.
- [x] **T019** [P] [US2] Test — revoked-grant renewal fails closed; assert no static-token fallback
      occurred.

**Checkpoint**: headless is safe and unattended renewal works. These two together are what make the
feature usable in CI and in scheduled work.

---

## Phase 4: US4 — The negatives, proven constructively (P1)

Each guard in this phase needs a **negative self-check**: break the property once, confirm the guard
goes red, restore. A guard that has never been seen to fail is not evidence.

- [x] **T020** [US4] Static guard — no module under `src/loopplane` binds a listening socket, opens a
      browser, or spawns a process (C1.3). Shape it like the existing boundary guards in
      `tests/contract/`.
- [x] **T021** [US4] Negative self-check for T020.
- [x] **T022** [US4] Test — a full flow against a temporary working directory creates **zero** files;
      plus a static guard on `oauth.py` (C4.2).
- [x] **T023** [US4] Negative self-check for T022.
- [x] **T024** [US4] Non-leakage sweep — one flow, then assert a token-shaped sentinel appears in no
      event, tool descriptor, tool result, gateway error, log record, capability record, or
      checkpoint (C6.1, C6.2).
- [x] **T025** [US4] **`git add` the sentinel fixture before trusting
      `tests/contract/test_public_safety.py`** — it enumerates through `git ls-files`, so an untracked
      fixture yields a false green (C6.4). This is the units-051/082 failure mode.
- [x] **T026** [P] [US4] Test — `repr`/`str` of the in-memory store and of every material-carrying
      object exclude material, so a traceback cannot leak (C6.3).
- [x] **T027** [P] [US4] Test — authorization is absent from every tool descriptor, and the model can
      neither start nor observe a flow (C7).
- [x] **T060** [US4] **Negative self-check for T024** — plant the sentinel into one emission path,
      confirm the sweep goes red, restore. *Added at analyze: T020 and T022 had self-checks and the
      non-leakage sweep did not, which is the guard most likely to pass by matching nothing.*

**Checkpoint**: the three negatives are guarded and each guard has been observed failing.

---

## Phase 5: US5 — Sign-out (P2)

- [x] **T028** [US5] Discard material for a `(principal, server)`; the next connection requires
      authorization (C4.4).
- [x] **T029** [P] [US5] Test — discard of absent material succeeds and reveals nothing.

---

## Phase 6: The managed capability surface (US6 prerequisite)

**⚠️ Exposed-interface change.** This is what makes `architecture-reviewer` mandatory (FR-019).

- [x] **T030** [US6] Add the authorization mode and the `needs_authorization` status to
      `ManagedMcpConfiguration` in `src/loopplane/host/capabilities.py` (C8.1) — **status only, never
      material** (C8.2), because this record is persisted inside the profile root and therefore
      inside the backup whitelist.
- [x] **T031** [US6] Carry the mode into `MCPServerConfig` in
      `src/loopplane/host/_capability_mcp.py:326-333`, which today passes only name / transport / url.
- [x] **T032** [US6] Thread the mode through the managed-MCP methods in `src/loopplane/host/host.py`.
- [x] **T033** [US6] Regenerate `tests/contract/fixtures/capability_surface.json` **deliberately** and
      review the diff as a contract change (C8.3).
- [x] **T034** [P] [US6] Test — `tests/integration/test_mcp_oauth_capability.py`: the managed surface
      round-trips the mode and status, and the persisted record contains no material.
- [x] **T035** [P] [US6] Test — the Web surface is byte-unchanged (C8.4).

---

## Phase 7: US6 — Desktop (P1 delivery)

Adding a sidecar method touches six registries plus their pins; the list is in
[research.md](research.md) R7.

- [x] **T036** [US6] `apps/desktop/electron/mcp-oauth-vault.ts` — `safeStorage` persistence under
      `app.getPath("userData")`, **outside** the profile root; refuse to store when
      `isEncryptionAvailable()` is false; no plaintext fallback (C9.2). Follow
      `provider-credentials.ts`'s vault/IO seam so it is unit-testable without Electron.
- [x] **T037** [US6] `apps/desktop/electron/mcp-oauth-flow.ts` — open the system browser, run the
      loopback listener, validate `state`, hand the result back (C9.1).
- [ ] **T038** [US6] Sidecar: implement both runtime Protocols in
      `apps/desktop/sidecar/methods/capability.py`.

      **Protocol shape, settled during implementation — read before starting.** Research R8 assumed
      the sidecar could push the authorization URL to main over the existing `EventEmitter`. It
      cannot, cheaply: `CapabilityMethods` holds no emitter, and outbound notifications are
      enumerated in the dispatcher's `NOTIFICATIONS` registry, which is part of the versioned stdio
      protocol ADR 0015 gates. Extending that is a larger, separately-reviewable change.

      Use **three request-direction methods instead**, so the notification enumeration and the
      `initialize` capability list are untouched:

      1. `mcp.authorize {mcp_id, redirect_uri}` → `{request_id}`. Starts the connect in a background
         task and returns immediately; the sidecar's handler records the URL that `present()`
         receives and blocks in `await_result()`.
      2. `mcp.authorize_status {request_id}` → `{state, url?, material?}` where `state` is
         `awaiting` / `authorized` / `failed`. Main polls this to learn the URL, then to learn the
         outcome, and takes the serialized material to persist.
      3. `mcp.authorize_complete {request_id, code, state}` → resolves the blocked handler.

      Plus `mcp.reconnect` gains an optional `material` so main can inject what it decrypted.
      Polling is less elegant than a push, but it stays inside the one direction the protocol
      already has, and its blast radius is three method names rather than the event contract.
- [ ] **T039** [US6] Register the new methods in `apps/desktop/sidecar/bridge.py`
      `_DESKTOP_METHOD_NAMES` (the `mcp.*` block, currently lines 442-446), and update the pinned
      method count in `tests/contract/test_desktop_rpc_v1.py:186` from 64 to 67 — deliberately, as a
      protocol change, not as a number that drifted.
- [ ] **T040** [US6] Wire `apps/desktop/electron/{ipc-channels,ipc-handlers,sidecar-rpc,main}.ts`.
- [ ] **T041** [US6] Renderer service in `apps/desktop/src/services/capability-services.ts` — the
      projection is `{server, mode, state}` only, no hint characters (C9.3).
- [ ] **T042** [US6] `packages/cowork-presentation/src/components/settings/McpSettings.tsx` plus i18n
      — mode selection, the three states, and a connect action.
- [ ] **T043** [P] [US6] Test — `tests/contract/test_desktop_public_safety_routing.py` and
      `tests/integration/test_desktop_sidecar.py` extended for the new methods.
- [x] **T044** [P] [US6] Vitest — vault refuses when encryption is unavailable; the renderer never
      receives a value; `apps/desktop/electron/__tests__/helpers.ts` and
      `apps/desktop/src/__tests__/sidecar-rpc.test.ts` updated.
- [ ] **T045** [US6] Test — a profile backup archive contains no material, proven from the placement
      in T036 rather than from a backup-side exclusion rule (C9.4).
- [ ] **T046** [US6] Test — restart reconnects without a new approval (C9.5).
- [ ] **T061** [US6] Disconnect from the settings surface discards the stored material; reconnecting
      requires approval again, with no stale material left behind. *Added at analyze — US6 acceptance
      scenario 3 had runtime coverage (T028/T029) but no Desktop-level task.*
- [ ] **T062** [P] [US6] Test — the whole Desktop path needs **zero** configuration files edited,
      environment variables set, or Python written (SC-010). *Added at analyze.*

---

## Phase 8: Documentation

- [ ] **T047** [P] `docs/capabilities.md` and `docs/gap-analysis.md` — G12 moves from "partially
      closed" to closed; remove the "MCP interactive OAuth" line from the P1 forward roadmap.
- [ ] **T048** [P] `docs/desktop-gui.md` — the new settings behaviour.
- [ ] **T049** [P] `CHANGELOG.md` `[Unreleased]` — unit 084.
- [x] **T050** `docs/api-reference.md` — the two new public Protocols, keeping the reference
      bijection the repo's contract test enforces.
- [ ] **T063** [P] Record the **rollback path** (C10.3, Constitution X): the feature is inert unless a
      host supplies both seams and a server declares the mode, so reverting is removing the seams —
      no data migration, no schema change. *Added at analyze: Principle X requires rollback guidance
      to be documented, and it existed only inside ADR 0019's consequences.*

---

## Phase 9: Final review

- [ ] **T051** Four gates: `ruff format --check`, `ruff check`, `mypy src`, `pytest` — run through
      **PowerShell**, never Bash (a Bash PATH override displaces System32 PowerShell and produces
      ~64 false failures in `tests/contract/test_desktop_delivery_gate.py`). Never run two pytest
      processes concurrently: the shared `tmp/pytest` base inside the repo causes WinError 32.
- [ ] **T052** `uv lock` **only if `pyproject.toml` changed** — which FR-018 says it should not.
      Verify with `uv lock --check`; the local gates run against an existing `.venv` and cannot see
      lock drift, while CI's first step `uv sync --locked` will.
- [ ] **T053** Public-safety scan over the changed files, including untracked ones.
- [ ] **T064** Assert the extras membership is unchanged via `tests/contract/test_packaging.py`
      (C10.2, FR-018). The `oauth` extra belongs to unit 056 — token *verification* — and must not be
      reused or renamed for this feature; `loopplane[oauth]` meaning two unrelated things would be a
      worse outcome than a new extra. *Added at analyze.*
- [ ] **T054** **`code-reviewer`** — mandatory (FR-019).
- [ ] **T055** **`architecture-reviewer`** — mandatory, because Phase 6 changes an exposed interface
      (FR-019, FR-020).
- [ ] **T056** Reconcile the test count item by item against the baseline — pytest 2236 passed /
      33 skipped, `tests/contract` 482 passed / 13 skipped — so an accidentally skipped or dropped
      test cannot hide inside a larger total.
- [ ] **T057** Set ADR 0019 to `Accepted` if that has not already happened at T000, and update
      `docs/loopplane-agent-board.md` §3 and §4 for unit 084.

**Known local flake**: `tests/integration/test_desktop_restore.py` (`restore.commit`) fails
intermittently under load and has never failed in CI. Rerun that file in isolation before treating it
as a regression. The TTL hypothesis is disproven — do not re-investigate it.

---

## Dependencies

```text
T000 (ADR accepted) ─── blocks everything
  └─ Phase 1 (seams) ─── blocks every story
       ├─ Phase 2 (US1 authorize)
       │    └─ Phase 3 (US3 fail closed → US2 renew)
       │         ├─ Phase 4 (US4 negatives)
       │         └─ Phase 5 (US5 sign-out)
       └─ Phase 6 (capability surface) ─── blocks Phase 7 (US6 Desktop)
                                              └─ Phase 8 (docs) ─ Phase 9 (review)
```

Phase 4 can start once Phase 2 lands, but its sweep is only complete once Phase 3 exists. Phase 6 is
independent of Phases 2–5 in code but depends on Phase 1's configuration mode.

## Note on task numbering

T058–T064 were added by the analyze pass to close coverage gaps and are placed in the phases they
belong to, so IDs are not contiguous within a phase. Each carries an *"Added at analyze"* note saying
what it closes. Nothing was renumbered, because a renumber across 65 tasks would break every
reference for no gain.

## Parallel opportunities

`[P]` tasks within a phase touch different files. The largest genuine parallel blocks are the test
tasks in Phases 2–5, and T036/T037 in Phase 7 (two new independent Electron modules).
