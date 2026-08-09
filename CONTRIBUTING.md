# Contributing to LoopPlane

Thanks for your interest in LoopPlane! This project is a spec-first, embeddable
control plane for loop-engineered AI agents, and contributions of all kinds —
bug reports, documentation, tests, and code — are welcome.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — open an issue using the bug report template. A minimal,
  runnable reproduction is the single most helpful thing you can include.
- **Propose a feature or change** — open an issue using the feature request
  template first, so we can align on the design before code is written.
- **Improve docs** — fixes to the guides under `docs/` and the runnable
  `examples/` are always appreciated.
- **Send a pull request** — for anything beyond a trivial fix, please open or
  comment on an issue first so the approach can be discussed.

For security issues, **do not open a public issue** — see [SECURITY.md](SECURITY.md).

## Development setup

LoopPlane targets **Python 3.12+** and standardizes on
[uv](https://github.com/astral-sh/uv).

```sh
git clone https://github.com/norton77930/loopplane.git
cd loopplane
uv sync          # installs the runtime plus the test/lint/type toolchain
```

A deterministic, credential-free scripted model ships with the runtime, so you
can run the smallest example without any API keys:

```sh
uv run python examples/host_quickstart.py
```

## Quality gates

Every change must pass the same gates CI runs. Please run them locally before
opening a pull request:

```sh
uv run ruff format --check .   # formatting
uv run ruff check .            # linting
uv run mypy                    # strict type checking
uv run pytest                  # tests
```

- The codebase is **`mypy --strict`** clean; new code is expected to be fully
  typed.
- New behavior needs tests. Bug fixes should come with a test that fails before
  the fix and passes after it.

## Project conventions

- **Spec-first.** LoopPlane is built spec-first: substantial changes trace to a
  spec, plan, and task list under `specs/`. For small fixes this is not required,
  but for new features or behavior changes please discuss the design in an issue
  first. Maintainers may ask for a short spec for larger work.
- **Surgical changes.** Keep pull requests focused. Touch only what the change
  requires, and match the surrounding style, naming, and test patterns.
- **Component boundaries.** The runtime has strict boundaries — one tool gateway,
  one normalized event bus. Please respect these rather than routing around them.
- **Commit messages** follow a Conventional-Commits-style prefix, e.g.
  `feat: …`, `fix: …`, `docs: …`, `test: …`, `refactor: …`.
- **Some "flaws" are load-bearing.** A few things in this codebase look like
  defects and are not. Read the hazard map below before cleaning any of them up.

## Hazard map — what looks broken but is not

This section exists because the most likely first pull request from a newcomer is
a well-intentioned cleanup of something that is deliberate. Each item below is a
documented compromise with a test or a rule behind it. If you think one of them
is genuinely wrong, that is a fine conversation — open an issue and make the
case. Please do not open a PR that "fixes" it first.

### 1. The quarantined imports are deliberate — never hoist them

Two places in the runtime import across a boundary in a way that looks untidy:

- `src/loopplane/context.py` imports from `loopplane.tools` **only** under
  `if TYPE_CHECKING:`. This is the wall that keeps `loop`, `controller`, and
  `engineering` from depending on `tools` at runtime: the file defines neutral
  Protocols, and the type-only import exists purely so those Protocols can be
  typed. Hoisting it to a top-level import creates a real import cycle across the
  whole controller/tools/assembly chain.
- `src/loopplane/host/assembly.py` imports concrete implementations **inside
  functions** (lazy imports). This is the single composition root, and the
  laziness is what keeps the package importable when optional extras are not
  installed — plus it breaks the `engineering → host → assembly` cycle.

Both are recorded as risks **R1** and **R4** in
`docs/architecture/RISK_REGISTER.md`, precisely because an IDE "organize imports"
action or a linter instinct makes them look like mistakes. Nothing appears broken
statically after you hoist them; things break at import time in environments that
differ from yours.

**Rule:** never convert a `TYPE_CHECKING` or function-scoped import in these
files to a top-level import. Verify with
`python -c "import loopplane.host"` in an environment with no extras installed.

### 2. Boundary-guard tests are the specification, not the obstacle

`tests/contract/test_*_boundary.py` (and a few in `tests/integration/`) are
AST-based guards that assert which packages may import which. They are derived
from `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md`, which is normative.

If a guard fails on your branch, the import is wrong — not the guard. Adding an
allowance to a guard is a boundary change and needs a maintainer decision first
(see the gates below). The guards also carry negative self-tests, so a guard that
cannot fail is itself treated as a bug.

### 3. Human approval gates come before implementation

Some changes need an explicit maintainer decision **before** code is written:
event or checkpoint schema changes, Tool Gateway SPI or stage-order changes, any
default-value change, new dependencies or install extras, outward
HTTP/SSE/WebSocket contract changes, and releases. The full list is §E of
`docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`; what each gate means and
how a decision is recorded is in [`GOVERNANCE.md`](GOVERNANCE.md).

A high-quality PR that trips a gate without a prior decision will still be asked
to stop and discuss. Opening the issue first costs you far less than the rework.

### 4. New behavior is additive and off by default

A new option must leave behavior **byte-identical when it is unset**. That is why
so many capabilities are gated behind a `RuntimeConfig` field defaulting to
`None` or `0`. Changing an existing default is a behavior change for every
existing deployment, and it is a gated decision — not a tidy-up.

Related invariants worth knowing before you refactor:

- `SCHEMA_VERSION` and `RECORD_SCHEMA_VERSION` are versioned contracts.
- Tools execute **only** through `ToolGateway`; nothing else may call `.invoke()`.
- `EventSink` is the only outbound event seam; consumers never re-emit it.
- No re-exports are added to the top-level `src/loopplane/__init__.py`.

### 5. Every committed file must be public-safe

The project treats public safety as a hard constraint (Constitution VII), and
`tests/contract/test_public_safety.py` enforces it repository-wide. Before you
push, check that your diff contains no:

- secrets, API keys, tokens, or private key material — including in tests and
  fixtures;
- absolute local paths from your machine, or private network addresses;
- internal or third-party proprietary names, or pasted non-public material.

Use placeholders and relative, repository-rooted paths in documentation and
examples.

### 6. Documentation is written in English

All committed documentation, comments, and commit messages are in English, so a
single audience can review the whole repository. Guides under `docs/guides/` are
navigational only: where they disagree with `docs/api-reference.md` or
`docs/capabilities.md`, the reference wins and the guide is the bug.

## Pull request process

1. Fork the repository and create a branch from `main`.
2. Make your change, with tests and docs as appropriate.
3. Ensure all four quality gates pass locally.
4. Open the pull request, fill in the template, and link any related issue.
5. A maintainer will review. Please be responsive to feedback; small, iterative
   PRs are easier to review and merge than large ones.

## License

By contributing, you agree that your contributions will be licensed under the
project's [MIT License](LICENSE). Contributions are accepted on an
inbound=outbound basis: what you submit is licensed under the same terms as the
project, and no separate contributor license agreement is required.
