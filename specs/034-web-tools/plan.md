# Implementation Plan: Web Tools (web_fetch + web_search) with Network-Egress Governance

**Branch**: `034-web-tools` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/034-web-tools/spec.md`

## Summary

Add two additive **NETWORK** tools on a new **Web Tool Adapter**
(`src/loopplane/tools/web.py`) — `web_fetch` (fetch an `http(s)` URL to readable
text, with a per-session in-memory cache) and `web_search` (run a query through a
**host-injected** `SearchProvider`, no bundled key) — each reachable **only
through the Tool Gateway** (Constitution V). Gate network egress with an
additive **`ToolDescriptor.network` flag** (default `False`; the two web tools
set it) and a **`network_policy` decider** that denies network-flagged tools
unless the host opts in, composed through the **existing** decide-stage
combinators (`all_of` deny-wins + `safe_failure` fail-closed) in
`host/assembly.py::_build_decider` — **no new gateway stage**. The egress toggle
is an additive, public-safe `RuntimeConfig.allow_network` flag (default `False`).
`httpx` becomes a declared **optional extra** (`net`), imported lazily inside
`web_fetch`. The change is purely additive: no gateway-pipeline, event-bus, loop,
or existing-tool change, and the core install gains no required dependency.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Standard library (`urllib.parse` for scheme guarding)
plus the **optional** `httpx` extra (`net`), imported lazily and only when network
egress is enabled. `anyio`/`pydantic` are already in core. No bundled search
provider, no API key.

**Storage**: N/A — the fetch cache is an in-memory `dict[(session_id, url), str]`
owned by the adapter; nothing is persisted.

**Testing**: pytest (offline, deterministic), mirroring
`tests/unit/test_internal_file_tools.py` (the `_context`/`_invoke` harness,
`pytest.mark.anyio`) and `tests/governance_helpers.py` (`call`/`descriptor`/`decide`).
The transport is mocked and the provider is a stub; a live check is opt-in /
secret-gated under `tests/live/` (excluded from default gates).

**Target Platform**: Cross-platform library runtime (Windows/macOS/Linux)

**Project Type**: Single project — embeddable Python library/runtime

**Performance Goals**: Interactive single-call latency; a per-session cache avoids
duplicate fetches; the Gateway's existing per-call timeout + output sizing bound
runaway calls (no new mechanism).

**Constraints**: Core install must not require `httpx`; no secret in `RuntimeConfig`
or the repo; no raw transport internal may leak across the Gateway boundary;
network egress default-deny (opt-in).

**Scale/Scope**: One new adapter module (two tool handlers + descriptors + the
provider Protocol), one new tiny governance module (`network_policy`), one
additive `ToolDescriptor` field, one additive `RuntimeConfig` flag wired in
`_build_decider`, one optional extra in `pyproject.toml`, plus deterministic unit
tests and one opt-in live test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Spec-First**: PASS. Plan traces to spec 034; tasks will trace to this plan.
- **II — Greenfield**: PASS. New code written fresh; no legacy code copied.
- **III — Harness Before Loop Automation**: PASS. No scheduler/evaluator/auto-iteration; this is tool + governance surface only.
- **IV — Runtime Boundary Clarity**: PASS. The web tools live behind the Tool Gateway adapter SPI; the network policy is a decide-stage `PolicyDecider` composed in the existing host decider builder. No reach-through; no boundary blurred.
- **V — Tool Gateway Ownership** (key gate): PASS. Both tools are registered as a `ToolAdapter` and are resolved, authorized, executed **only** through the Gateway; no bypass path. Every failure (bad URL, timeout, transport error, missing provider, missing `httpx`) is returned as `ErrorOutput` / a normalized error — raw exceptions never cross the boundary. The network gate is enforced at the existing decide stage, not a new chokepoint.
- **VI — Event Bus**: PASS. No event schema change; tools emit existing `TextBlock`/`ErrorOutput` only.
- **VII — Public-Safe**: PASS (key gate). No bundled API key, no secret in `RuntimeConfig` (a single boolean `allow_network`); error messages are scrubbed of credentials, headers, and raw transport objects; the search provider (and its credential) is host-supplied.
- **VIII / IX — No SDK Replacement / Reference-not-clone**: PASS. No agent framework adopted; `httpx` is a plain HTTP client behind a lazy import; the web-tool semantics are re-derived in LoopPlane's own adapter.
- **X — Testable Evolution**: PASS. Deterministic offline tests (mocked transport + stub provider) plus an opt-in live check; rollback is deletion of the adapter, the `network` field, the `network_policy`, the `allow_network` flag, and the extra (all additive, reversible).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/034-web-tools/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── tools.md         # Tool input/output + provider/policy contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/loopplane/
├── tools/
│   ├── web.py               # NEW: WebToolAdapter — web_fetch + web_search;
│   │                        #   SearchProvider Protocol + SearchResult; the
│   │                        #   per-session fetch cache; lazy httpx import.
│   └── __init__.py          # MODIFY: export WebToolAdapter, SearchProvider,
│                            #   SearchResult (additive __all__)
├── governance/
│   ├── network.py           # NEW: network_policy(*, allow_network) — denies a
│   │                        #   network-flagged descriptor unless egress is on
│   └── __init__.py          # MODIFY: export network_policy (additive __all__)
├── model/
│   └── boundary.py          # MODIFY: ToolDescriptor +network: bool = False
├── host/
│   ├── config.py            # MODIFY: RuntimeConfig +allow_network: bool = False
│   │                        #   (+ from_mapping coercion); no secret
│   └── assembly.py          # MODIFY: _build_decider composes network_policy via
│                            #   the existing all_of + safe_failure combinators
├── gateway/
│   └── spi.py               # USE (unchanged): AdapterOutput, ErrorOutput
└── errors.py                # USE (unchanged): ErrorCategory.VALIDATION/EXECUTION

pyproject.toml               # MODIFY: [project.optional-dependencies] +net = ["httpx>=0.27"]
                             #   (dev group already has httpx; core unchanged)

tests/
├── unit/
│   ├── test_web_tools.py        # NEW: deterministic offline tests for
│   │                            #   web_fetch (mocked transport) + web_search
│   │                            #   (stub provider) + cache + error normalization
│   └── test_network_policy.py   # NEW: network_policy deny-by-default / allow-on-
│                                #   opt-in / non-network untouched / fail-closed
├── contract/
│   └── test_host_config.py      # MODIFY (additive): allow_network wiring →
│                                #   network tool denied off / allowed on
└── live/
    └── test_live_web.py         # NEW: opt-in, secret-gated real web_fetch
                                 #   (skipped unless LOOPPLANE_WEB_LIVE set)
```

**Structure Decision**: Single-project library layout. The network concern is
kept **cohesive in a new `tools/web.py` module** (not folded into the offline
`internal.py`), wired into the Gateway via `register_adapter` exactly like
`InternalToolAdapter`. The governance gate is a new tiny `governance/network.py`
policy composed through the **existing** `_build_decider` combinators. No new
package, no frontend, no new gateway stage.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
