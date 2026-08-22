# Phase 1 Data Model: MCP Interactive OAuth

Two rules govern everything below and are worth stating before the entities:

1. **Material is never configuration and never a record.** Configuration carries a *mode*; records
   carry a *status*. Neither ever carries a value.
2. **The only durable thing is stored authorization material, and `src/loopplane` never writes it.**

## Configuration

### `MCPServerConfig` (modified — `adapters/mcp/config.py`)

| Field | Change | Notes |
| ----- | ------ | ----- |
| `auth_token: str \| None` | unchanged | ADR 0007 D3 static bearer |
| `authorization: str \| None` | **new** | The authorization *mode*. `None` = today's behaviour. The only value this unit defines is interactive authorization. |

Validation, added to the existing `_check_transport_fields` model validator:

- `authorization` set **and** `auth_token` set → invalid (ADR 0019 D4, mutually exclusive).
- `authorization` set on `stdio` or `websocket` → invalid.
- An invalid entry disables **only itself**: `merge_layers` already reports and skips a malformed
  entry, leaving a valid same-named definition from a broader layer in place. That behaviour is
  reused unchanged, not re-implemented.

The config carries **no** client id, client secret, token, scope secret, or redirect URI value. Client
identity is either discovered by dynamic registration or supplied by the host through the store.

## Runtime seams (new — `adapters/mcp/oauth.py`)

### `McpAuthorizationHandler` (Protocol, host-implemented)

| Member | Shape | Responsibility |
| ------ | ----- | -------------- |
| `present(url, *, server, principal)` | async, returns nothing | The host shows or opens the authorization URL. The runtime never does. |
| `await_result(*, server, principal)` | async, returns `(code, state)` | The host returns what the redirect delivered. The runtime never listens. |

Absent (`None`) means **no interactive authorization is possible** in this process. That is the
headless default and it fails closed (FR-015) — it is not a degraded mode.

### `McpTokenStore` (Protocol, host-implemented)

Keyed by `(principal_id, server_name)` on every operation — the isolation unit (ADR 0019 D5).

| Member | Shape | Responsibility |
| ------ | ----- | -------------- |
| `load(principal, server)` | async, returns material or `None` | Read stored material. |
| `save(principal, server, material)` | async | Persist, including after a refresh. |
| `discard(principal, server)` | async | Sign-out. Succeeds when nothing is stored, revealing nothing. |

### `InMemoryMcpTokenStore` (the only implementation shipped)

Process-lifetime `dict` keyed by `(principal, server)`. The default when a host supplies none.
Writes nothing to disk. Its `__repr__` and every string form must exclude material — a `dataclass`
with a default `repr` would leak into a traceback.

### `StoredAuthorizationMaterial`

Not a public content type and never an event payload. The one durable entity in the unit; on Desktop
it lives only inside Electron main's encrypted blob.

| Field | Purpose |
| ----- | ------- |
| `tokens` | The SDK's token model, kept opaque — nothing in the runtime formats it |
| `client_info` | The SDK's registered-client model, equally opaque |
| `expires_at` | **Absolute** unix expiry of the access token, or `None` when the server did not say |

`expires_at` exists because the SDK restores tokens from storage but not their expiry, so without it
a restarted process sends dead material, takes a 401, and runs a **full re-authorization** instead of
a silent refresh — a browser prompt in a job with nobody attached. It is recorded when the SDK stores
a token and restored onto the provider afterwards. An unknown expiry stays `None`: a guess would
expire a working token. See the ADR 0019 implementation note.

### Transient values (never persisted, never emitted)

| Value | Lifetime |
| ----- | -------- |
| authorization URL | until presented |
| `state` | until the result is validated; compared in constant time; consumed at most once |
| PKCE verifier | until token exchange |
| authorization code | until token exchange |

## Host capability surface

### `ManagedMcpConfiguration` (modified — `host/capabilities.py`)

| Field | Change | Notes |
| ----- | ------ | ----- |
| `id`, `name`, `transport`, `url` | unchanged | |
| `status` | unchanged shape, **new member** | gains `needs_authorization` alongside `connected` / `disconnected` / `invalid` |
| `authorization` | **new** | the mode; `None` for an ordinary server |
| `tools`, `tool_count`, `problem`, `updated_at` | unchanged | `problem` stays a fixed public-safe string |

**This record is persisted by `CapabilitySettingsStore` inside the LoopPlane profile root, which is
inside the backup whitelist.** It therefore carries mode and status and never material (ADR 0019 D8).
That is the single most important line in this document.

`tests/contract/fixtures/capability_surface.json` pins the managed-capability method signatures and
must be regenerated deliberately when `upsert_managed_mcp` and its siblings gain the mode.

## Desktop

### Electron main — the encrypted blob

Separate from the ADR 0016 provider-credential blob, same placement discipline: under
`app.getPath("userData")`, **outside** the LoopPlane profile root, so `sidecar/archive.py`'s
whitelist cannot sweep it into a backup by construction. Versioned like `provider-credential.bin`.
Refuses to store anything when `safeStorage.isEncryptionAvailable()` is false — no plaintext
fallback, exactly as ADR 0016 D2.

### Renderer projection

The only shape allowed to cross to the renderer:

| Field | Values |
| ----- | ------ |
| `server` | the server id |
| `mode` | `none` \| `interactive` |
| `state` | `authorized` \| `needs_authorization` \| `failed` |

No token, no expiry timestamp precise enough to fingerprint, no hint characters. ADR 0016's
`PublicProviderView` allows a four-character hint for a provider key; this projection allows none,
because nothing in the MCP settings surface needs one.

## What is deliberately absent

- No new content block, no event type, no `SCHEMA_VERSION` change — authorization is never something
  the model sees (Constitution VI untouched).
- No new checkpoint field.
- No `RuntimeConfig` knob: the seams are adapter constructor parameters (ADR 0019 D2), keeping
  `RuntimeConfig` out of the credential path.
- No credential in `MCPServerConfig`, in `ManagedMcpConfiguration`, or in any committed fixture other
  than a deliberately tracked sentinel used to prove non-leakage.
