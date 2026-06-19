# Quickstart: Validating Web Tools + Network-Egress Governance

This guide proves the two network tools and the egress gate work end-to-end
through the Tool Gateway. All default scenarios are offline and deterministic
(mocked transport + stub provider); the live fetch is opt-in and secret-gated.

## Prerequisites

- A dev install of the repo (`uv sync` / `pip install -e ".[dev]"`), Python 3.12+.
  The `dev` group already includes `httpx`, so the offline tests run without the
  `net` extra.
- No API key and no network are needed for the default gate.

## Automated validation (primary)

Run the new offline tests plus the governance core to confirm no regression:

```powershell
uv run pytest tests/unit/test_web_tools.py tests/unit/test_network_policy.py tests/contract/test_host_config.py -q
```

Then the full quality gates:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

**Expected**: all green; every existing tool / descriptor / policy test unchanged.

## What the tests assert (mapping to acceptance scenarios)

- **Network policy** (US1): a network-flagged descriptor is **denied** when egress
  is off (US1-1) and **allowed** when on (US1-2); a non-network descriptor is never
  denied (US1-3); a raising policy in the composed chain still denies — fail-closed
  (US1-4).
- **`web_fetch`** (US2): a mocked transport returns the body text and records a cache
  entry (US2-1); a second fetch of the same URL does not call the transport again
  (US2-2); a non-`http(s)`/malformed URL is a `VALIDATION` error with no fetch
  (US2-3); a timeout / transport error is a normalized error with no secret (US2-4);
  a missing `httpx` degrades to a normalized error.
- **`web_search`** (US3): a stub provider's results render as text (US3-1); no
  provider yields a clear "not configured" `VALIDATION` error (US3-2); a raising
  provider yields a normalized error with no leaked internals (US3-3).
- **Assembly wiring**: a `RuntimeConfig(allow_network=False)` builds a decider that
  denies a network tool; `allow_network=True` allows it (deny-wins with any approval
  policy).

## Opt-in live check (excluded from default gates)

A single real fetch is skipped unless explicitly enabled:

```powershell
$env:LOOPPLANE_WEB_LIVE = "1"; uv run pytest tests/live/test_live_web.py -q
```

It installs nothing automatically — run it only with the `net` extra present
(`uv pip install httpx` or `pip install ".[net]"`).

## Manual smoke (optional)

Construct a `WebToolAdapter` (optionally with a `search_provider` and/or a fake
`fetcher`), register it on a `ToolGateway` whose `decide` is
`network_policy(allow_network=True)` composed via `safe_failure`/`all_of`, and
invoke each tool through a `RunContext`. See `contracts/tools.md` for the exact
input/output contract and `data-model.md` for the schemas.

To wire it through the host, pass the adapter in `RuntimeConfig.tool_adapters` and
set `allow_network=True`:

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.tools import WebToolAdapter

host = LoopPlaneHost(
    RuntimeConfig(
        model=model,
        tool_adapters=(WebToolAdapter(search_provider=my_provider),),
        allow_network=True,
    )
)
```

Leaving `allow_network` at its default (`False`) makes the agent's network calls
deny at the Gateway — the safe default.

## Rollback

The feature is additive. To roll back, remove `src/loopplane/tools/web.py` and its
exports, `src/loopplane/governance/network.py` and its export, the
`ToolDescriptor.network` field, the `RuntimeConfig.allow_network` field, the
`_build_decider` network-policy composition, the `net` extra in `pyproject.toml`,
and the new test modules; the baseline tool set, the gateway, and every policy are
untouched (Constitution X).
