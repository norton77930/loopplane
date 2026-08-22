# Contract: MCP Interactive OAuth

The behavioural contract for unit 084. Every clause is stated so a test can fail it.

## C1 — The runtime initiates; the host acts

1. When a configured `http` or `sse` server declares interactive authorization and no valid stored
   material exists, the adapter MUST produce an authorization URL and pass it to the host's
   authorization handler.
2. The adapter MUST then await the host's authorization result and MUST NOT proceed without it.
3. During the whole flow the runtime MUST NOT open a browser, spawn a process, or bind a listening
   socket. **Enforced constructively** by a static guard over `src/loopplane`, not only by observing
   a test run.
4. On success the server's tools MUST be registered exactly as an unauthenticated server's tools are
   today — same descriptors, same qualified naming, same Gateway pipeline.

## C2 — `state` and PKCE

1. The flow MUST use the authorization-code grant with PKCE.
2. The `state` returned by the host MUST be compared against the value the runtime issued, in
   constant time.
3. A missing, empty, or mismatched `state` MUST fail the connection, MUST discard the pending flow,
   and MUST NOT retry automatically.
4. An authorization result MUST be consumable at most once; a replayed result MUST fail on `state`.
5. Authorization MUST be bounded by a timeout, after which the pending flow is discarded and the
   server is left unconnected.

## C3 — Transport applicability

1. Interactive authorization MUST apply to `http` and `sse` only.
2. Declaring it on `stdio` or `websocket` MUST be rejected as invalid configuration.
3. `websocket` MUST remain as ADR 0007 D3 left it — no header auth, no `auth` handler, unchanged.
4. Declaring interactive authorization together with the 059 `auth_token` MUST be rejected.
5. Every rejection in this section MUST disable **only the offending entry**, leaving other servers —
   and a valid same-named definition from a broader configuration layer — in place.

## C4 — Storage

1. The runtime MUST define the token-store Protocol and MUST ship exactly one implementation, held in
   memory for the process lifetime.
2. **No code under `src/loopplane` may write authorization material to disk under any configuration.**
   Verified by running a full flow against a temporary working directory and asserting the runtime
   created no file, and by a static guard on the OAuth module.
3. Every store operation MUST be keyed by `(principal, server)`. A read for one principal MUST NOT
   return another principal's material; a read for one server MUST NOT return another server's.
4. Discarding material MUST make the next connection require authorization again, and MUST succeed —
   revealing nothing — when nothing was stored.

## C5 — Renewal and failure

1. Given valid refresh material, renewal MUST succeed **without** invoking the host's authorization
   handler. A test MUST assert the handler's invocation count is zero.
2. A failed renewal MUST disconnect the server and report that re-authorization is needed.
3. A failed renewal MUST NOT attempt an unauthenticated connection and MUST NOT fall back to the 059
   static token.
4. With **no** authorization handler configured, a server declaring interactive authorization MUST NOT
   connect and MUST NOT attempt any connection without a credential.
5. Every failure in this section MUST be contained to its own server: other servers connect and their
   tools remain available, per the existing 057/059 isolation.

## C6 — Non-leakage

1. No access token, refresh token, authorization code, client secret, or PKCE verifier may appear in:
   a runtime event, a tool descriptor, a tool input or output, a gateway error, a log record, a
   capability record, a checkpoint, or an exported archive.
2. Errors MUST carry a fixed public-safe message; no error may echo any part of a credential.
3. The in-memory store and every material-carrying object MUST NOT expose material through `repr`,
   `str`, or a default dataclass representation — a traceback is a leak path.
4. The proving test MUST use a token-shaped sentinel, and the fixture carrying it **MUST be
   git-tracked**, because `tests/contract/test_public_safety.py` enumerates through `git ls-files` and
   would otherwise report a false green.

## C7 — The model is outside the flow

1. Authorization MUST NOT be registered as a tool and MUST NOT appear in any tool descriptor.
2. No credential may be a tool argument or any part of a tool result.
3. The model MUST NOT be able to start, observe, redirect, or cancel a flow.
4. No content-model type and no event schema changes; `SCHEMA_VERSION` is unchanged.

## C8 — The managed capability surface

1. The managed-MCP surface MUST be able to express the authorization mode, which today it cannot.
2. The persisted managed record MUST carry mode and status only — `authorized` /
   `needs_authorization` / `failed` — and MUST NOT carry material. This record lives inside the
   profile root and therefore inside the backup whitelist.
3. `tests/contract/fixtures/capability_surface.json` MUST be regenerated deliberately as part of this
   change and reviewed as a contract change.
4. The Web surface MUST be byte-unchanged.

## C9 — Desktop

1. Electron main MUST own opening the browser, receiving the redirect, and persisting material.
2. Material MUST be encrypted through `safeStorage` and stored under `app.getPath("userData")`,
   outside the LoopPlane profile root. When `isEncryptionAvailable()` is false, nothing is stored and
   no plaintext fallback is offered.
3. The renderer MUST receive only `{server, mode, state}`. No token, no hint characters.
4. A profile backup archive MUST NOT contain material — provable by construction from the placement in
   C9.2, not by a backup-side exclusion rule.
5. After a successful authorization, closing and reopening the app MUST reconnect without a new
   approval.

## C10 — Additivity

1. A configuration with no interactive server MUST behave exactly as the current release, including
   the ADR 0007 static-token path.
2. No new runtime dependency and no new extra. The existing `oauth` extra belongs to unit 056
   (token *verification*) and MUST NOT be reused or renamed for this feature.
3. The feature MUST be reversible by removing the two seams: no data migration, no schema change.
