# ADR 0016: Desktop collects and stores a model-provider credential

- **Status**: **Accepted** (2026-08-15) — the maintainer accepted the Desktop divergence from the Web
  stance recorded for unit 075, and chose to widen the sidecar import allow-list (D5) rather than
  leave the edge invisible.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. It narrows, for the Desktop surface only, the
  project-wide position that a LoopPlane UI does not collect provider credentials.
- **Related**: **ADR 0015** (Desktop cowork process/profile/presentation boundary), Constitution
  **I** (implementation traces to an approved artifact — this ADR is that artifact), **VII**
  (public-safe diagnostics), **VIII** (a boundary-blurring change updates the boundary definition),
  **IX** (durability ownership), **X** (default-preserving, testable, reversible).
  `docs/loopplane-agent-board.md` records for unit 075 that "Browser UI still does not collect
  provider credentials".

## Context

LoopPlane is an embeddable agent-harness runtime: the embedder brings a model
(`README.md`, `docs/model-providers.md`). Desktop inherited that stance literally.
`apps/desktop/sidecar/bridge.py::select_desktop_model` reads `LOOPPLANE_MODEL` as a
`module:attribute` reference to a Python builder and, absent one, returns a `DemoModel` that answers
every prompt with `"LoopPlane demo model: no provider is configured."`

None of the 33 sidecar JSON-RPC methods concerns a model, provider, or credential, and no credential
storage exists anywhere in `apps/desktop`. The consequence is that a person who installs the packaged
app, opens it, and types gets a placeholder reply, and the only remedy is to set a Python import path
in an environment variable before launching an Electron application.

That is coherent for a runtime, and incoherent for a desktop application — particularly one intended
to be usable by people who do not write Python. Web is genuinely different: it is served to a browser
the operator does not control, over a network boundary, to a principal who is not necessarily the
machine's owner. Desktop is a local application, run by the machine's owner, with an OS keystore
available and no network listener.

## Decision

- **D1 — Desktop collects a provider credential; Web still does not.** The divergence is deliberate
  and bounded to the Desktop surface. Nothing in `apps/web`, the web/API host, or the runtime changes.

- **D2 — Electron main owns the credential; the sidecar never persists it.** Main encrypts with
  Electron's `safeStorage` (OS keystore: DPAPI, Keychain, libsecret) and refuses to store anything
  when `isEncryptionAvailable()` is false. A plaintext fallback is not offered.

- **D3 — The blob lives outside the LoopPlane profile root**, under `app.getPath("userData")`.
  Backups assemble from a profile whitelist (`apps/desktop/sidecar/archive.py`), so a credential
  stored outside the profile cannot enter an archive by construction. The `"credentials"` exclusion
  already disclosed by `apps/desktop/sidecar/backup.py` therefore stays true with no backup-side rule,
  and `backup.describe`'s disclosure text is unchanged.

- **D4 — The credential reaches the sidecar as spawn environment, not as an RPC parameter.** No
  sidecar method is added, `_DESKTOP_METHOD_NAMES` is unchanged, and the initialize capability
  enumeration is unchanged, so the versioned stdio protocol of ADR 0015 is untouched. A packaged-smoke
  run is excluded from the injection and keeps its scripted model.

- **D5 — The sidecar import allow-list admits `loopplane.adapters`, and the adapters are imported
  statically.** Constitution VIII requires that a change blurring a boundary update the boundary
  definition rather than route around it. `tests/contract/test_desktop_boundary.py` previously
  permitted only `loopplane.host`, `loopplane.events`, `loopplane.errors`, and `loopplane.model`, so
  an earlier draft of this change reached the adapters through `importlib`.

  That was rejected. The adapter packages need no lazy import to be loadable — each SDK is imported
  inside its client factory — so `importlib` bought nothing at runtime, and its only practical effect
  was that the AST scan could not see a real edge. `RUNTIME_ALLOWED_PREFIXES` therefore gains
  `loopplane.adapters` with a "model construction only" note, and each provider builder takes a normal
  `from loopplane.adapters.… import …`. The imports stay inside the builder functions: the scan walks
  the whole AST, so they remain visible to the audit, while `main()` still answers `initialize` from a
  lightweight dispatcher before anything expensive loads.

  The pre-existing `LOOPPLANE_MODEL` path still resolves an operator-named module through `importlib`.
  That is unchanged and inherently outside the audit; it is an operator-only escape hatch, not a
  product path.

- **D6 — An in-app setting outranks `LOOPPLANE_MODEL`; a packaged-smoke scenario outranks both.**
  When an operator has exported `LOOPPLANE_MODEL` *and* a user has saved a provider in the app, the
  saved provider wins and the builder reference is ignored without warning.

- **D7 — A provider change takes effect by relaunching the app.** `RuntimeConfig.model` is a frozen
  field consumed into `LoopPlaneHost`, and the sidecar holds the profile ownership lock; relaunching
  is the one path that rebuilds both without a partial teardown. No in-place model swap and no proxy
  `ModelBoundary` is introduced.

- **D8 — The key is write-only from the renderer's side.** `providers.get` answers with
  `{provider, modelId, hasKey, keyHint}` where `keyHint` is at most the last four characters. Save
  failures are a fixed enumeration (`encryption_unavailable`, `invalid_provider`, `invalid_model_id`,
  `missing_key`, `write_failed`); no OS text, path, or exception message crosses the boundary.

## Consequences

**Accepted cost.** The credential is decrypted in Electron main and passed to a child process
environment. A process running as the same user can read either the environment or the encrypted file
plus the keystore, so this raises no new attacker class beyond what local user compromise already
grants. It is also the mechanism `docs/model-providers.md` already documents for every host.

**Reversible.** Removing `apps/desktop/electron/provider-credentials.ts`, the four `lp:providers:*`
channels, the preload group, the settings tab, and the `select_desktop_model` branch restores the
previous behavior exactly; the `LOOPPLANE_MODEL` path is retained unchanged for operators.

**Not decided here.** Model catalogue retrieval, per-session model switching, several providers
configured at once, and cost/usage surfacing on Desktop remain out of scope.

## Alternatives considered

- **Keep BYO-model.** Honest for a runtime, but leaves the packaged application unusable to its stated
  audience. Rejected because the desktop app is a product surface, not only a reference host.
- **Sidecar-owned storage.** Would place the credential in the profile the sidecar already owns, but
  Python has no OS keystore here, so it would mean hand-rolled encryption and a new backup exclusion
  rule. Rejected on both counts.
- **A `provider.configure` RPC with an in-place model swap.** Would avoid a relaunch, but requires a
  new protocol method, a new capability, a mutable `RuntimeConfig`, and a proxy `ModelBoundary` whose
  `context_capacity()` could change mid-session. Rejected as disproportionate to the benefit.
