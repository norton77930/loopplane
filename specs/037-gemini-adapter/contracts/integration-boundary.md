# Contract: Integration Boundary

How unit 037 attaches to the repository without changing the runtime core, the
content model, or the event schema — and the consistency contracts it keeps green.

## No core / content-model / event-schema change

- The adapter implements the **existing** `ModelBoundary`; no file under
  `src/loopplane/{loop,controller,gateway,events,model,host}` changes behavior.
- **The content model is unchanged**: `src/loopplane/model/content.py` is not
  edited (`ToolCallBlock` gains no signature field).
- **The event schema is unchanged**: no `SCHEMA_VERSION` bump; only normalized
  increments cross the loop seam (Constitution VI).
- The SDK enters **only** as a model-boundary adapter (Constitution VIII): the
  runtime core is not delegated to an external framework.

## Optional extra + lazy import

- `pyproject.toml` gains one optional extra: `gemini = ["google-genai>=1"]`. The
  **runtime dependency set is unchanged** (`anyio + pydantic + jsonschema`).
- The dev dependency group adds `google-genai` so `mypy --strict` and the offline
  tests can type-check and exercise the adapter — **unless** the wheel cannot be
  resolved offline, in which case the import stays lazy + the extra declared and the
  offline stub tests carry the unit (exactly as unit 020 does when its SDKs are
  absent; an unresolvable optional dep must not block the gates).
- The adapter imports its SDK **lazily** (inside the client factory), so
  `import loopplane.adapters.gemini` succeeds with the SDK uninstalled (the
  packaging import contract imports every public subpackage).

## Consistency contracts to keep green

- **`docs/api-reference.md`**: add one `### \`loopplane.adapters.gemini\`` section
  listing exactly that package's `__all__` (`GeminiConfig`, `GeminiModel`); the
  api-reference drift contract (`tests/contract/test_api_reference.py`) compares it.
- **`CHANGELOG.md`**: add a `037` entry under Added after `036` (keeps the
  Keep-a-Changelog structure).
- **`docs/real-model-validation.md`**: extend with the opt-in Gemini live-check env
  vars (`GEMINI_API_KEY` + `LOOPPLANE_GEMINI_MODEL`).
- **`tests/live/test_live_models.py`**: the live Gemini turn is `skipif`-gated on
  those env vars and **excluded from CI** (CI references no `secrets.`).
- **public-safety scan**: every new committed file (code, docs, specs) is free of
  secrets, private IPs, and absolute user paths.

## Rollback

Delete `src/loopplane/adapters/gemini/`, `tests/unit/test_gemini_mapping.py`, the
Gemini entries in `tests/integration/provider_stubs.py` /
`tests/unit/test_capabilities.py` / `tests/live/test_live_models.py`; revert the
additive edits to `pyproject.toml`, the api reference, the changelog, and
`docs/real-model-validation.md`. The core, the content model, the event schema, the
scripted model, and units 020/035/036 are untouched.
