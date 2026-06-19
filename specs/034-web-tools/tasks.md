---
description: "Task list for Web Tools (web_fetch + web_search) with network-egress governance (spec 034)"
---

# Tasks: Web Tools (web_fetch + web_search) with Network-Egress Governance

**Input**: Design documents from `/specs/034-web-tools/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tools.md

**Tests**: REQUIRED (Constitution X). Write tests FIRST and confirm they FAIL
before implementing each unit. Every default test is offline and deterministic
(mocked transport + stub provider); the live test is opt-in / secret-gated.

**Organization**: Grouped by user story (US1 network-egress policy P1, US2
`web_fetch` P2, US3 `web_search` P3). US1 is the foundation (the gate must exist
before the network tools are safe to ship). The two tool handlers land in one new
module (`tools/web.py`), so their *implementation* tasks are sequential; the
governance policy lands in its own module and is independent.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The additive descriptor field, the optional extra, and the test harness.

- [ ] T001 In `src/loopplane/model/boundary.py`, add `network: bool = False` to `ToolDescriptor` (additive, after `read_only`/before `source`); no other change.
- [ ] T002 In `pyproject.toml`, add `net = ["httpx>=0.27"]` to `[project.optional-dependencies]` (leave the existing `web` FastAPI extra and the `dev` group — which already has `httpx` — unchanged).
- [ ] T003 Create `tests/unit/test_web_tools.py` with shared fixtures/helpers (a temp `working_scope`, a `_context(tmp_path)`, an `_invoke(...)` drainer of `invoke()` output, a fake `fetcher`, and a stub `SearchProvider`), mirroring `tests/unit/test_internal_file_tools.py` (`pytest.mark.anyio`).

**Checkpoint**: The descriptor field exists; the extra is declared; the test module is ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `WebToolAdapter` skeleton so tests can target the tools.

**⚠️ CRITICAL**: Must complete before any user-story implementation.

- [ ] T004 Create `src/loopplane/tools/web.py` with `SearchResult` (frozen pydantic model), the `SearchProvider` Protocol, the `WebToolAdapter` class (`__init__(*, search_provider=None, fetcher=None)`, the per-session `_cache`, `describe()` returning the two `network=True` descriptors with the schemas from `data-model.md`, an `invoke()` handler map to `_web_fetch`/`_web_search` stubs, and `shutdown()` clearing the cache). Export `WebToolAdapter`, `SearchProvider`, `SearchResult` from `src/loopplane/tools/__init__.py` (additive `__all__`).

**Checkpoint**: Both tools resolve through the gateway; TDD can begin.

---

## Phase 3: User Story 1 - Network egress denied by default, opt-in (Priority: P1) 🎯 MVP

**Goal**: `network_policy` denies network-flagged tools unless the host opts in, composed deny-wins + fail-closed through the existing combinators.

**Independent Test**: Build the policy with egress off/on and a network/non-network descriptor; assert deny/allow; make a composed policy raise and assert deny.

### Tests for User Story 1 ⚠️ (write first, must FAIL)

- [ ] T005 [US1] Create `tests/unit/test_network_policy.py` (using `tests/governance_helpers.py` `call`/`descriptor`/`decide`): (a) `allow_network=False` + a `network=True` descriptor → `PolicyDeny`; (b) `allow_network=True` + `network=True` → `PolicyAllow`; (c) `network=False` descriptor → `PolicyAllow` under both settings; (d) `safe_failure(all_of(network_policy, <raising policy>))` → `PolicyDeny` (fail-closed); (e) `all_of(network_policy(False), allow_all)` → deny-wins.
- [ ] T006 [US1] In `tests/contract/test_host_config.py`, add failing assembly tests (additive): a `RuntimeConfig(allow_network=False)` with a registered `network=True` tool builds a decider that **denies** that tool; `allow_network=True` **allows** it; a non-network tool is unaffected; `from_mapping({... "allow_network": True})` round-trips.

### Implementation for User Story 1

- [ ] T007 [US1] Create `src/loopplane/governance/network.py`: `network_policy(*, allow_network: bool) -> PolicyDecider` built with `as_decider` — deny a `descriptor.network` tool when `not allow_network`, else allow; never deny a non-network descriptor. Export `network_policy` from `src/loopplane/governance/__init__.py` (additive `__all__`).
- [ ] T008 [US1] In `src/loopplane/host/config.py`, add `allow_network: bool = False` to `RuntimeConfig` (after `observability`) and coerce it in `from_mapping` (`bool(data.get("allow_network", False))`); confirm no secret field is introduced.
- [ ] T009 [US1] In `src/loopplane/host/assembly.py::_build_decider`, compose the network gate through the **existing** combinators: build `network_policy(allow_network=config.allow_network)` and return `safe_failure(all_of(<approval decider if any>, network_policy))`. Preserve the existing `None` fast-path only when egress is the default *and* there is no approval/skills *and* no network-capable adapter (otherwise return the composed decider so network tools are denied by default).
- [ ] T010 [US1] Run `uv run pytest tests/unit/test_network_policy.py tests/contract/test_host_config.py -q` and confirm all US1 tests pass.

**Checkpoint**: The egress gate is enforced by default and opt-in — the foundation the web tools depend on.

---

## Phase 4: User Story 2 - Fetch a URL to readable text, cached per session (Priority: P2)

**Goal**: `web_fetch` returns body text, caches per session, and normalizes every failure.

**Independent Test**: Mocked fetcher → body text + cache entry; repeat → no second call; bad scheme / timeout / transport error / missing httpx → normalized error.

### Tests for User Story 2 ⚠️ (write first, must FAIL)

- [ ] T011 [US2] In `tests/unit/test_web_tools.py`, add failing `web_fetch` tests: (a) success — a fake fetcher returns `(200, body)` → `TextBlock(body)` and a cache entry; (b) cache hit — a second identical fetch does **not** increment the fetcher's call count; (c) per-session scoping — a different `session_id` re-fetches; (d) non-`http(s)` scheme (`file://`) and a malformed URL → `VALIDATION`, fetcher never called; (e) timeout → `EXECUTION` error, no secret in message; (f) transport error → `EXECUTION`; (g) non-2xx status → `EXECUTION` with the code; (h) missing `httpx` (default fetcher path, simulated) → normalized error naming the `net` extra.

### Implementation for User Story 2

- [ ] T012 [US2] Implement `_web_fetch` in `src/loopplane/tools/web.py`: parse + scheme-guard the URL (`urllib.parse`; non-`http(s)`/malformed → `VALIDATION`); check `_cache[(session_id, url)]`; otherwise call `self._fetcher` (or the lazily-built `httpx` default — wrap `import httpx` in `try/except ImportError → ErrorOutput`); map timeout/transport/non-2xx to a normalized `EXECUTION` `ErrorOutput` (scrubbed message); on success store the cache and yield `TextBlock`.
- [ ] T013 [US2] Run `uv run pytest tests/unit/test_web_tools.py -k fetch -q` and confirm all US2 tests pass.

**Checkpoint**: `web_fetch` fully functional, cached, and fail-safe.

---

## Phase 5: User Story 3 - Search via a host-pluggable provider (Priority: P3)

**Goal**: `web_search` renders provider results and degrades cleanly when unconfigured.

**Independent Test**: Stub provider → rendered results; no provider → "not configured"; raising provider → normalized error.

### Tests for User Story 3 ⚠️ (write first, must FAIL)

- [ ] T014 [US3] In `tests/unit/test_web_tools.py`, add failing `web_search` tests: (a) stub provider returns results → `TextBlock` containing each title + url; (b) provider returns `[]` → explicit "no results" `TextBlock`; (c) no provider configured → `VALIDATION` "not configured"; (d) provider raises → `EXECUTION` error with no leaked internals; (e) `limit` is passed through to the provider (default 5).

### Implementation for User Story 3

- [ ] T015 [US3] Implement `_web_search` in `src/loopplane/tools/web.py`: if `self._search_provider is None` → `VALIDATION` "web search is not configured"; else `await provider.search(query, limit=limit)` inside `try/except Exception → EXECUTION` (scrubbed); render results as `title — url` (+ snippet) lines, or an explicit "no results" message.
- [ ] T016 [US3] Run `uv run pytest tests/unit/test_web_tools.py -k search -q` and confirm all US3 tests pass.

**Checkpoint**: Both web tools independently functional behind the egress gate.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T017 Add `tests/live/test_live_web.py`: a single opt-in, secret-gated real `web_fetch` (skipped unless `LOOPPLANE_WEB_LIVE` is set), mirroring `tests/live/test_live_models.py`; excluded from the default gate.
- [ ] T018 Regression: run `uv run pytest tests/unit/test_rules_and_tools.py tests/contract/test_tool_gateway.py tests/contract/test_webapi_boundary.py -q` and confirm the existing tools, gateway, and webapi `ToolView` are unchanged by the additive `network` field.
- [ ] T019 Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green.
- [ ] T020 Run the `quickstart.md` validation commands and confirm expected outcomes.
- [ ] T021 [P] Update `CHANGELOG.md` (a `- **034**` entry after 033), `docs/loopplane-agent-board.md` (a `034-web-tools` Verified row + §4 Active Feature → 035 next), `CLAUDE.md` (SPECKIT block → `specs/034-web-tools/plan.md`), and `.specify/feature.json` (`specs\\034-web-tools`).

---

## Dependencies & Execution Order

- **T001–T003 (Setup)** → **T004 (Foundational, blocks all stories)** → stories.
- **US1 (T005–T010)** is the foundation: the egress gate must exist and be tested before the network tools ship. **US1 → US2 → US3.**
- Within each story: tests (T005/T006, T011, T014) FAIL first → implementation → verify.
- US2 and US3 implementation both edit `tools/web.py` (sequential); US1's policy is a separate module (`governance/network.py`) but is sequenced first by priority.
- **Polish (T017–T021)** after all three stories.

## Parallel Opportunities

- Limited: the two tool handlers share `tools/web.py` (serialized). The governance
  policy (`governance/network.py`) and the descriptor field/extra are independent of
  the tool bodies. T021 (tracking-doc updates) is `[P]` (different files).

## Implementation Strategy

- **MVP** = Phase 1 + 2 + Phase 3 (US1 network-egress policy) — the safety
  foundation, independently shippable and the precondition for the tools.
- Then add US2 (`web_fetch`), US3 (`web_search`) incrementally; each leaves the
  baseline set and every existing policy intact.

## Notes

- One new **optional** dependency (`httpx`, the `net` extra), imported lazily; the
  core install is unchanged. No frontend, no event/gateway/loop change, no new
  gateway stage (the network gate reuses the existing decide-stage combinators).
- No secret anywhere: the search credential lives in the host-supplied provider, not
  in `RuntimeConfig` or the repo; fetch error messages are scrubbed.
- Commit after the sprint spec is green (main-only autopilot), message via `git commit -F`.
- Rollback = delete `tools/web.py` + `governance/network.py` + their exports, the
  `network` field, the `allow_network` flag, the `_build_decider` composition, the
  `net` extra, and the new test modules.
