---
description: "Task list for unit 016 — LoopPlane Plugin System"
---

# Tasks: LoopPlane Plugin System

**Input**: Design documents from `specs/016-loopplane-plugin-system/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Write each test FIRST and confirm it FAILS
before the matching implementation.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `src/loopplane/plugins/` with an empty `__init__.py` placeholder.

---

## Phase 2: Foundational — manifest, discovery, loader (BLOCKS user stories)

- [ ] T002 [P] Unit test `tests/unit/test_plugins_manifest.py`: `PluginManifest`
  requires `name`/`version`, accepts optional `skills`/`mcp_servers`/`hooks`,
  forbids extra keys, and `HookEntry` carries `point`/`target` (FR-002). (FAIL first)
- [ ] T003 [P] Unit test `tests/unit/test_plugins_discovery.py`: `discover(roots)`
  finds subdirs with a `plugin.json`, ignores those without, returns a public-safe
  `problem` for an unparseable manifest, and **never raises** (FR-001/FR-008/FR-009).
  (FAIL first)
- [ ] T004 Implement `src/loopplane/plugins/manifest.py` — `PluginManifest` +
  `HookEntry` (pydantic, `extra="forbid"`, frozen) and a parse helper.
- [ ] T005 Implement `src/loopplane/plugins/discovery.py` — `discover(roots)` →
  `list[DiscoveredPlugin]`, broadest-first, never raises. Depends on T004.
- [ ] T006 Implement `src/loopplane/plugins/loader.py` — `load_plugins(roots,
  enabled, *, hook_registry=None) -> PluginLoadResult` (gate → collect skill_dirs →
  namespaced `mcp_layer` → register hooks via the bounded enabled-only import →
  skip-whole-plugin + problems) and `list_plugins(roots, enabled)` (public-safe).
  Depends on T004/T005.
- [ ] T007 Implement `src/loopplane/plugins/__init__.py` public surface (`__all__`).
  Depends on T004–T006.

**Checkpoint**: package imports; manifest + discovery unit tests pass.

---

## Phase 3: User Story 1 — discover and load an enabled plugin (P1) 🎯 MVP

- [ ] T008 [US1] Integration test `tests/integration/test_plugins_us1.py`: a valid
  enabled plugin loads with its contributions; a directory without a `plugin.json`
  is ignored (FR-001, SC-001). (FAIL first → passes via Phase 2.)

---

## Phase 4: User Story 2 — enable only trusted plugins (P1)

- [ ] T009 [US2] Integration test `tests/integration/test_plugins_us2.py`: with two
  discovered plugins and one enabled, only the enabled one's contributions are
  collected; with an empty enable-list, the result is empty (FR-003/FR-004, SC-002).
  (FAIL first)

---

## Phase 5: User Story 3 — a plugin contributes skills (P2)

- [ ] T010 [US3] Integration test `tests/integration/test_plugins_us3.py`: an enabled
  plugin's skill directories are collected and load through the existing
  `loopplane.skills.load_skills`, indistinguishable from host skills (FR-005, SC-006).
  (FAIL first)

---

## Phase 6: User Story 4 — a plugin contributes MCP servers and hooks (P2)

- [ ] T011 [US4] Integration test `tests/integration/test_plugins_us4.py`: an enabled
  plugin's MCP server `s` is collected as `<plugin>__s` for `merge_layers`
  (SC-005); its hook (`{point, target}`, target an importable test module) is
  registered on a supplied `HookRegistry` (FR-006/FR-007). (FAIL first)

---

## Phase 7: User Story 5 — malformed / unsafe plugins are handled safely (P3)

- [ ] T012 [US5] Integration test `tests/integration/test_plugins_us5.py`: a
  malformed manifest skips the whole plugin while others load; a credential-bearing
  manifest is skipped; an enabled name with no match is noted; cross-root name
  collision resolves by precedence; `list_plugins` leaks nothing; nothing raises
  (FR-008/FR-009/FR-010/FR-011/FR-012/FR-014). (FAIL first)

---

## Phase 8: Boundary, public-safety, and polish

- [ ] T013 [P] Boundary test `tests/integration/test_plugins_boundary.py`:
  `loopplane.plugins` imports only `loopplane.skills` / `loopplane.adapters.mcp` /
  `loopplane.hooks` (plus stdlib/pydantic); it adds no parameter to and changes no
  contract of those units, executes no tool, and emits no event (FR-013).
- [ ] T014 [P] Public-safety test `tests/integration/test_plugins_public_safety.py`:
  manifests, listings, and diagnostics carry no secret, credential, or private path
  (FR-010, SC-004).
- [ ] T015 [P] Add `examples/plugins_quickstart.py` — credential-free discover →
  load → apply walkthrough (quickstart.md).
- [ ] T016 [P] Add `docs/plugins.md` — the plugin guide.
- [ ] T017 Update `docs/api-reference.md` with the `loopplane.plugins` public names
  (unit-014 `test_api_reference` enforces the `__all__` bijection).
- [ ] T018 Update `docs/README.md` and `examples/README.md` indexes for the new
  guide/example (unit-014 `test_docs_examples_index` enforces index↔tree).
- [ ] T019 Run `ruff format --check`, `ruff check`, `mypy` (strict), and the full
  `pytest` suite; fix to green.
- [ ] T020 Final review: set unit 016 to **Verified** in
  `docs/loopplane-agent-board.md` (§3 row + §4) and commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (manifest → discovery → loader → `__init__`) blocks the user
  stories. US1–US5 (Phases 3–7) then exercise `load_plugins` end-to-end and are
  independently testable. Phase 8 depends on the desired stories; T017/T018 are
  required for the unit-014 release contracts to stay green.

### Parallel opportunities

- T002/T003 (unit tests) run in parallel.
- T013–T016 (boundary/safety tests, example, docs) run in parallel.

## Notes

- The plugin system **consumes** the existing seams; it adds no parameter to and
  changes no contract of units 001/008/015 (additive — FR-013).
- The hook contribution uses a bounded, **enabled-only** import of the manifest's
  `target`; tests supply an importable target module.
- With an empty enable-list / no root, nothing is collected or registered, so the
  un-plugged runtime is unchanged (FR-004/FR-015/SC-002).
