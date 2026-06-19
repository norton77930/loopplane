# Phase 0 Research: Web Tools (web_fetch + web_search)

All decisions favour reuse of the existing Tool Gateway adapter SPI and the
existing `governance` combinators, a default-deny network posture, and a
dependency-light core with `httpx` as an optional, lazily-imported extra. No
NEEDS CLARIFICATION remained from the spec.

## Decision 1 — A new `tools/web.py` module, not an extension of `internal.py`

- **Decision**: The web tools live in a new `WebToolAdapter`
  (`src/loopplane/tools/web.py`), registered with the Gateway via
  `register_adapter` exactly like `InternalToolAdapter`.
- **Rationale**: The network concern is distinct from the offline, dependency-light
  file tools: it carries an optional dependency (`httpx`), a host-injected provider
  seam, and a network-egress gate. Keeping it in its own module keeps `internal.py`
  free of an optional import and keeps the network surface cohesive and individually
  rollback-able (Constitution X).
- **Alternatives considered**: Extend `InternalToolAdapter` (rejected: pulls an
  optional `httpx` import and a provider seam into the offline baseline tools,
  blurring the dependency-light contract).

## Decision 2 — `ToolDescriptor.network: bool = False` as the gate signal

- **Decision**: Add an additive boolean `network` to `ToolDescriptor` (default
  `False`); `web_fetch`/`web_search` set `network=True`; the network policy decides
  purely from this descriptor flag.
- **Rationale**: The descriptor is already the decide-stage's source of truth
  (`read_only`, `concurrency_safe`, `source`); a `network` flag is the consistent,
  metadata-only way to mark egress without inspecting tool names or inputs. Adding a
  defaulted field is non-breaking — every existing descriptor and test keeps working
  (the webapi `ToolView` and host inspection read named fields, not the whole set).
- **Alternatives considered**: A name allow-list in the policy (rejected: brittle,
  couples the policy to specific tool names); a separate registry of "network tools"
  (rejected: a second source of truth diverging from the descriptor).

## Decision 3 — `network_policy` composed via the existing combinators (no new stage)

- **Decision**: Add `governance/network.py::network_policy(*, allow_network)` built
  with `as_decider` (decides from the descriptor alone). In
  `host/assembly.py::_build_decider`, compose it with the existing approval decider
  using `safe_failure(all_of(approval, network_policy))` from
  `loopplane.governance.combine` — **deny-wins** (`all_of`) + **fail-closed**
  (`safe_failure`). The Gateway's decide stage is unchanged.
- **Rationale**: The brief mandates reusing the existing decide-stage seam, not a new
  gateway chokepoint (Constitution V). `all_of` already short-circuits on the first
  deny and `safe_failure` already maps any raise to a deny — exactly the deny-wins +
  fail-closed semantics required. This mirrors `governance/sandbox.py::sandbox_profile`,
  which composes policies the same way.
- **Alternatives considered**: A new Gateway stage (rejected: violates "reuse the
  existing seam" and adds a chokepoint); wiring the policy directly without
  `safe_failure` (rejected: a raising policy could fall through — not fail-closed).

## Decision 4 — `_build_decider` returns a decider whenever egress is gated

- **Decision**: `_build_decider` currently returns `None` (allow-all) when there is
  no approval policy and no skills. It now **also** builds a decider when network
  egress is **off** and the runtime can register network tools, so a network tool is
  denied even in the bare/test posture. When egress is on, the network policy allows
  network tools and the approval decider (if any) still applies (deny-wins). When
  there is nothing network-relevant *and* no approval/skills, it still returns `None`
  (unchanged behavior for the existing no-policy path).
- **Rationale**: Default-deny only works if the gate is present by default. Building
  the policy whenever egress is off preserves the safe-by-default posture; keeping the
  `None` fast-path when egress is the harmless default *and* no network tool can be
  registered avoids changing the existing allow-all test posture for non-network runs.
- **Alternatives considered**: Always return a decider (rejected: changes the
  allow-all default for every existing non-network run, a behavior change the brief
  forbids).

## Decision 5 — Per-session in-memory fetch cache

- **Decision**: A `dict[tuple[str, str], str]` keyed by `(session_id, url)`, owned by
  the adapter and cleared on `shutdown()`. A cache hit returns the stored text with no
  network call. Nothing is persisted; nothing is shared across sessions.
- **Rationale**: Matches the spec's "avoid refetch within a session" and the existing
  adapter pattern (the file adapter's `self._reads` is likewise an in-memory
  per-session map cleared on shutdown). Deterministic and trivial to test.
- **Alternatives considered**: A TTL/LRU cache (rejected: premature; per-session
  dedupe is the stated need); a cross-session cache (rejected: leaks one session's
  fetch into another, against the per-session scope).

## Decision 6 — `httpx` is an optional extra, imported lazily; the extra is `net`

- **Decision**: Add `[project.optional-dependencies] net = ["httpx>=0.27"]`. Import
  `httpx` **inside** `_web_fetch` (after the scheme guard) under `try: import httpx
  except ImportError: -> ErrorOutput`. Keep `httpx` in the `dev` group (already
  present) so the default gates can run the offline tests against a mocked transport.
- **Rationale**: The core install must not require `httpx` (FR-012); a lazy import +
  a normalized error is the established degradation pattern (cf. the optional model
  adapters importing `anthropic`/`openai` lazily). The existing `web` extra is already
  taken by FastAPI (unit 011), so a new `net` extra cleanly names the network-tool
  dependency without overloading `web`.
- **Alternatives considered**: Add `httpx` to the existing `web` extra (rejected:
  `web` is the FastAPI transport extra; conflating the two couples unrelated installs);
  make `httpx` a core dependency (rejected: violates the dependency-light core, FR-012);
  use stdlib `urllib.request` (rejected: blocking, no clean async, poorer ergonomics —
  and the dev/test toolchain already ships `httpx`, the established client).

## Decision 7 — Transport injection for deterministic tests

- **Decision**: `_web_fetch` resolves its fetch through a small injectable seam: the
  `WebToolAdapter` accepts an optional `fetcher` callable
  (`async (url, *, timeout) -> (status, text)`); when absent it lazily builds an
  `httpx`-backed default. Tests inject a fake `fetcher` (and assert call counts for
  the cache); production uses the real one. The search side is injected as the
  `SearchProvider` directly.
- **Rationale**: Keeps every default test offline and deterministic without
  monkeypatching `httpx` internals, and isolates the single optional-dependency call
  site. The seam is internal (constructor kwarg), not new public surface beyond the
  adapter + the provider Protocol.
- **Alternatives considered**: Monkeypatch `httpx.AsyncClient` in tests (rejected:
  brittle, couples tests to httpx internals); a global registry (rejected: hidden
  state).

## Decision 8 — Minimal `http(s)`-scheme guard, not a full SSRF policy

- **Decision**: `web_fetch` parses the URL and rejects any scheme other than `http`/
  `https` (and a malformed URL) with a `VALIDATION` error before any network call.
  Richer SSRF defenses (private-IP/allow-list/DNS-rebinding) are explicitly reserved.
- **Rationale**: The scheme guard is a cheap, high-value narrowing that blocks
  `file://`/`ftp://`/garbage; a full SSRF policy is a separate host-side concern out of
  scope here (spec Out of Scope) and would belong in a dedicated network policy.
- **Alternatives considered**: A full SSRF allow-list now (rejected: scope creep; the
  egress gate already makes network opt-in, and the host owns finer policy).

## Decision 9 — `web_search` provider seam shape

- **Decision**: `SearchProvider` is a `Protocol` with one method
  `async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]`;
  `SearchResult` is a frozen pydantic model (`title`, `url`, `snippet`). The host
  passes an instance to `WebToolAdapter(search_provider=...)`. No provider →
  `web_search` returns a `VALIDATION` "not configured" error. A raising provider →
  a normalized `EXECUTION` error.
- **Rationale**: One narrow async method keeps the seam trivial to implement and stub;
  a typed `SearchResult` keeps rendering deterministic and public-safe. The host (not
  LoopPlane) owns the credential, satisfying VII.
- **Alternatives considered**: A bundled provider (rejected: needs an embedded key,
  violates VII); a free-form `Callable` returning untyped dicts (rejected: weaker
  typing, harder to render/test).

## Decision 10 — Test layout

- **Decision**: Deterministic offline tests in `tests/unit/test_web_tools.py`
  (mocked fetcher + stub provider, mirroring `test_internal_file_tools.py`'s
  `_context`/`_invoke`/`pytest.mark.anyio`) and `tests/unit/test_network_policy.py`
  (using `tests/governance_helpers.py` `call`/`descriptor`/`decide`). An additive
  assembly test in `tests/contract/test_host_config.py` covers the `allow_network`
  wiring end-to-end at the decider. One opt-in, secret-gated live fetch in
  `tests/live/test_live_web.py` (skipped unless `LOOPPLANE_WEB_LIVE` is set),
  mirroring `tests/live/test_live_models.py`.
- **Rationale**: Consistent with the repo's existing tool/governance/live test
  patterns; no network, no credentials in the default gate; the live path is opt-in
  and excluded from default runs.
