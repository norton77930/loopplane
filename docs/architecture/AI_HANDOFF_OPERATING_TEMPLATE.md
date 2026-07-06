# AI Handoff Operating Template

> The start-of-work template for AI agents working on this repo. Used alongside `AGENTS.md` (workflow) and the constitution; on conflict: constitution > this file > everything else.

## A. Required reading order (before starting)

1. This file
2. `.specify/memory/constitution.md` (ten principles; IV–VI are the boundaries, VII is public-safety)
3. `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` (where to touch, which block to check)
4. `docs/loopplane-agent-board.md` (current state; the completion authority)
5. The active unit's `specs/<unit>/{spec,plan,tasks}.md`
6. When touching load-bearing areas: `ARCHITECTURE_AUDIT.md` + `RISK_REGISTER.md`
7. `AGENTS.md` (autopilot / commit rules). README last, and only as positioning reference.

## B. Source-of-truth priority

`src` + `tests` + `pyproject.toml` > board > `docs/api-reference.md` > `specs/064+` > capabilities/gap-analysis > CHANGELOG > README.
Untrustworthy fields: spec `Status:`, unchecked tasks boxes in older units (see `SPEC_KIT_ALIGNMENT_RULES.md` §9–10).

## C. Editing-before-inspection checklist (walk through before every edit)

1. Which block of `TARGET_ARCHITECTURE_BOUNDARIES.md` owns this file? Read its forbidden deps and AI cautions.
2. Is it load-bearing (`model/`, `errors.py`, `events/`, `context.py`, `gateway/`, `host/assembly.py`)? → grep inbound imports first to size the blast radius.
3. Read the package's `__init__.py` docstring and `__all__`.
4. Locate the matching tests (`test_<pkg>_core` / `test_<pkg>_boundary` / `test_<pkg>_us*`).
5. Does the change touch: a default value? an event/record schema? the gateway SPI? an outward HTTP contract? → if any yes, pass the human approval gate (§E) first.
6. Confirm no new dependency was introduced and no lazy/TYPE_CHECKING import was converted to top-level.

## D. Architecture invariants (ten-line summary)

1. Tools execute only through `ToolGateway`; SPI = describe/invoke/shutdown.
2. `EventSink` is the only outbound seam; consumers never re-emit.
3. `SCHEMA_VERSION` / `RECORD_SCHEMA_VERSION` are versioned contracts.
4. `loop`/`controller`/`engineering` never import `tools` (the `context.py` Protocols are the wall).
5. `orchestration` never imports `gateway`/`context`/`model`.
6. `host/assembly.py` is the single composition root; its lazy imports are deliberate.
7. New knobs are default-off and byte-identical when unset.
8. Base deps are only anyio/pydantic/jsonschema; extras use the four guard patterns.
9. `run_loop` is the only Phase-3 entry.
10. No re-exports are added to the top-level `loopplane/__init__.py`.

## E. Human approval gates (stop first, then ask)

- Event / checkpoint record schema changes; gateway SPI or stage-order changes; `PolicyVerdict` type changes.
- Loosening any Constitution IV–VI boundary; amending the constitution itself.
- New external dependencies / new extras; any default-value change.
- Outward webapi HTTP/SSE/WS contract changes (the apps depend on generated types).
- Releases (`__version__` / CHANGELOG / tag).
- Any operation that could touch `openspec/`, private paths, or credentials.

## F. Forbidden actions

- Modifying or committing `openspec/`; writing private paths/internal names/secrets into any committed file.
- Hand-editing `<!-- SPECKIT START/END -->` managed blocks.
- `git reset --hard`, force pushes, branch deletion; blind bulk `git add` (instead: reset → add files individually → review the staged list as a separate step → then commit).
- Changing `SCHEMA_VERSION`/`RECORD_SCHEMA_VERSION`, the gateway SPI, defaults, or dependencies without approval.
- Adding re-exports to `src/loopplane/__init__.py`; converting TYPE_CHECKING/lazy imports to top-level.
- Retro-editing Verified units' spec/tasks; inferring completion from spec `Status:` or old checkboxes.

## G. Verification commands

```
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest tests/unit/test_<pkg>*.py tests/contract/test_<pkg>_boundary.py -q   # targeted
uv run pytest -q                                                                   # full suite (60 s/test timeout)
```

- Known flakes: `tests/integration/test_examples_smoke.py` (timeouts under full-suite load) and `test_us2_mcp` (CPU contention) — on failure, re-run in isolation before drawing conclusions.
- Frontend: in `apps/web`, `npm run typecheck` + `npm run test` (vitest run); for `apps/desktop`, check its `package.json` scripts before running.
- Do not run the full pytest suite concurrently with multi-agent workflows (a historical source of MCP timeout flakes).

## H. Completion report format

1. What changed (one sentence + which files).
2. Verification: what was run and the literal results (including failures); what was skipped and why.
3. Whether any §E gate was touched, and the approval record.
4. Known limitations and follow-up risks.
5. Never claim what was not verified (targeted tests only ≠ "full suite passed").

## I. Rollback requirements

- Each unit / each patch = a single `git revert`-able commit (Constitution X requires rollback guidance).
- Schema/contract changes: write the forward/backward compatibility note before implementing.
- Docs-only changes: a revert is a complete rollback.
