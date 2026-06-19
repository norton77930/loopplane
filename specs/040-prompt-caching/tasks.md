# Tasks: Anthropic Prompt Caching (explicit cache breakpoints)

**Feature**: `040-prompt-caching` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Dependency-ordered, TDD-first (Constitution X). `[P]` = parallelizable.
All tests are deterministic and offline.

## Phase 1 — Failing tests first (TDD)

- [x] **T001** — `tests/unit/test_anthropic_caching.py` (NEW): write failing tests for
  `apply_prompt_caching` — (a) ON: last tool definition carries `cache_control:
  {"type":"ephemeral"}`; (b) ON: first message's last content block carries it
  when ≥2 messages, and the last message carries none; (c) ON: ≤4 breakpoints
  total; (d) ON degenerate: no tools → no tools marker; single message → no
  messages marker; empty first-content → no messages marker; (e) purity: inputs
  are not mutated. (Contracts C1–C5, C7.)
- [x] **T002** — In `tests/unit/test_anthropic_caching.py`, add a failing
  adapter-level test: `AnthropicModel(AnthropicConfig(..., prompt_caching=True))`
  drives a stub turn and the recorded `client.messages.create` kwargs carry the
  `cache_control` markers on tools + first message; with `prompt_caching=False`
  the kwargs `messages`/`tools` equal `build_messages`/`build_tools` exactly (no
  `cache_control`). (Contracts C1, C2, C5.)
- [x] **T003** [P] — In `tests/unit/test_openai_mapping.py`, add a test that a
  usage chunk with `prompt_tokens_details.cached_tokens=N` yields
  `TurnEnd.usage.cached_tokens == N`, confirming OpenAI passive caching is already
  reported and the request carries no cache parameter. (Contract C6.)

## Phase 2 — Implementation (make the tests pass)

- [x] **T004** — `anthropic/config.py`: add `prompt_caching: bool = True` to
  `AnthropicConfig` (additive field; document it inline). (FR-004.)
- [x] **T005** — `anthropic/mapping.py`: add `apply_prompt_caching(messages,
  tools)` — a pure overlay attaching `cache_control: {"type":"ephemeral"}` to the
  last tool (if any) and the first message's last content block (when ≥2 messages
  and non-empty content), copying the marked dicts (no in-place mutation), ≤2
  markers. `build_messages` / `build_tools` stay byte-identical. (FR-001/002/003/
  006.)
- [x] **T006** — `anthropic/adapter.py`: in `stream_turn`, when
  `self._config.prompt_caching`, run the assembled `messages`/`tools` through
  `apply_prompt_caching` before the client call (the only call site). When off,
  the request is unchanged. (FR-004/005.)

## Phase 3 — Docs & tracking

- [x] **T007** [P] — `docs/real-model-validation.md` §5: note the opt-in
  cache-savings observation (watch `cached_tokens` rise across two identical-prefix
  turns; offline gates unaffected). (FR-009.)
- [x] **T008** [P] — `CHANGELOG.md`: add a `- **040** ...` entry after `- **039**
  ...`.
- [x] **T009** [P] — `docs/loopplane-agent-board.md`: add a `040-prompt-caching`
  §3 row after the `039` row + update §4 (040 done; 041 configurable compaction is
  the next Tier-3 follow-on).
- [x] **T010** [P] — `.specify/feature.json` → `specs\\040-prompt-caching`;
  `CLAUDE.md` SPECKIT block → `specs/040-prompt-caching/plan.md`.

## Phase 4 — Gates (all green via the locked toolchain)

- [x] **T011** — `uv run ruff check .`
- [x] **T012** — `uv run ruff format .` then `uv run ruff format --check .`
- [x] **T013** — `uv run mypy` (src-only, strict → "Success")
- [x] **T014** — `uv run pytest -q` (prior 906 passed + the new caching/OpenAI
  tests; no existing test needs updating — the default-on rationale is in
  research.md Decision 2).

## Notes

- **No api-reference edit** (FR-010): no new public package/`__all__` name, so the
  unit-014 bijection (`tests/contract/test_api_reference.py`) stays green
  untouched.
- **Rollback** (Constitution X): `prompt_caching=False`, or revert
  `apply_prompt_caching` + the one `adapter.py` call → exact pre-caching behavior.
