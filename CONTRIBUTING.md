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
