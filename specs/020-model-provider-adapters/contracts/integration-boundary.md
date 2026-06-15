# Contract: Integration Boundary

How unit 020 attaches to the repository without changing the runtime core, and the
consistency contracts it must keep green.

## No core change

- The adapters implement the **existing** `ModelBoundary`; no file under
  `src/loopplane/{loop,controller,gateway,events,model,host}` changes behavior.
- The SDKs enter **only** as model-boundary adapters (Constitution VIII): the runtime
  core is not delegated to an external framework.

## Optional extras + lazy import

- `pyproject.toml` gains two optional extras: `anthropic = ["anthropic>=..."]` and
  `openai = ["openai>=..."]`. The **runtime dependency set is unchanged**
  (`anyio + pydantic + jsonschema`).
- The dev dependency group adds both SDKs so `mypy --strict` and the offline tests can
  type-check and exercise the adapters.
- Each adapter module imports its SDK **lazily** (inside the client factory), so
  `import loopplane.adapters.anthropic` / `...openai` succeeds with neither SDK installed
  (the packaging import contract imports every public subpackage).

## Consistency contracts to keep green

- **`tests/contract/test_packaging.py`**: the pinned optional-dependencies set becomes
  `{anthropic, mcp, openai, otel, web}`; the runtime-dependencies assertion is unchanged.
- **`docs/api-reference.md`**: add one `### \`loopplane.adapters.anthropic\`` section and
  one `### \`loopplane.adapters.openai\`` section, each listing exactly that package's
  `__all__` (the api-reference drift contract compares the two).
- **`docs/README.md`**: link the new `docs/model-providers.md` guide (docs-index
  contract).
- **`examples/README.md`**: list `anthropic_quickstart.py` and `openai_quickstart.py`
  (examples-index contract).
- **`CHANGELOG.md`**: add a `020` entry under Added (keeps the Keep-a-Changelog
  structure; the units-covered contract checks 001–013 only, so this is additive).
- **`.github/workflows/ci.yml`**: unchanged gate set; **no `secrets.` reference** — the
  live test stays out of CI.
- **public-safety scan**: every new committed file (code, docs, examples, specs) is
  free of secrets, private IPs, and absolute user paths.

## Rollback

Delete `src/loopplane/adapters/{anthropic,openai}/`, their tests, examples, and the
`docs/model-providers.md` guide; revert the additive edits to `pyproject.toml`, the api
reference, the indexes, the changelog, and the packaging test. The core and the scripted
model are untouched.
