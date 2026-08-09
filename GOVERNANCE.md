# LoopPlane governance

This document explains who decides what in LoopPlane, what the "maintainer approval"
gates referenced throughout the repository actually mean, and how decisions are recorded.
It is the outward-facing companion to the internal working rules in
[`AGENTS.md`](AGENTS.md) and
[`docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`](docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md).

If you are about to open a pull request, read [`CONTRIBUTING.md`](CONTRIBUTING.md) first —
especially its **hazard map**, which lists the deliberately kept compromises that must not
be "fixed".

## Project model

LoopPlane is maintained under a **benevolent-dictator** model with a single maintainer,
listed in [`.github/CODEOWNERS`](.github/CODEOWNERS). The maintainer has final say on
scope, architecture, and releases. Everything else about the project is designed to make
that authority legible rather than arbitrary: the rules are written down first, and both
humans and AI agents are held to the same written rules.

A large part of this codebase is produced by AI agents working from written specifications
under the same review gates as human contributions. That is why the repository carries an
unusual amount of machine-readable governance (a constitution, ADRs, boundary contracts, a
risk register). Outside contributors are not expected to work that way — but the gates
below apply to every change regardless of who or what wrote it.

## Roles

| Role | Who | Rights |
| --- | --- | --- |
| **Maintainer** | the account in `.github/CODEOWNERS` | Final decision on scope, architecture, dependencies, releases, and merges. Sole approver of the gates in the next section. |
| **Contributor** | anyone who opens an issue or pull request | Propose changes, review, discuss. Contributions are accepted inbound=outbound under the [MIT License](LICENSE). |
| **Automation** | CI workflows and the repository's contract tests | Enforce the mechanically checkable rules. CI can block a merge; it can never approve one. |

There are currently no additional formal roles (no committer tier, no steering group). If
the project grows enough to need them, they will be added here first.

## The approval gates

Several documents in this repository say a change "requires maintainer approval" or
"passes the §E gate". Those all refer to the same list, normatively defined in §E of
[`docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md`](docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md).
Concretely, a change needs an explicit maintainer decision **before** implementation when
it touches any of the following:

| Gate | What it covers | Why |
| --- | --- | --- |
| **Schema** | `SCHEMA_VERSION` / `RECORD_SCHEMA_VERSION`; any event or checkpoint record shape | The event stream and the checkpoint format are versioned outward contracts; consumers and persisted sessions depend on them. |
| **Tool Gateway SPI** | `describe()` / `invoke()` / `shutdown()`, the six-stage order, `PolicyVerdict` types | The Gateway is the single tool-execution chokepoint (Constitution V); a signature or stage change breaks every adapter at once. |
| **Boundaries** | loosening any Constitution IV–VI boundary, or amending the constitution | These boundaries are the architecture. Relaxing one is a design decision, not a refactor. |
| **Defaults** | changing any default value, or making a new option default-on | A new knob must be byte-identical when unset; changing a default silently changes every existing deployment. |
| **Dependencies** | new runtime dependencies, new dev dependencies, new install extras | The base dependency set is deliberately three packages; everything else is an optional extra behind a guarded import pattern. |
| **Outward web/API contract** | HTTP / SSE / WebSocket routes, payloads, and status codes of `loopplane.webapi` | The web and desktop apps depend on generated types derived from this contract. |
| **Releases** | version bump, changelog promotion, tag, publish | See [`docs/release-process.md`](docs/release-process.md). |
| **Confidentiality** | anything touching private paths, credentials, or non-public reference material | Constitution VII: every committed file must be public-safe. |

**How to pass a gate.** Open an issue (or comment on the existing one) describing the
change, which gate it trips, and why it is necessary. Wait for the maintainer's explicit
decision before writing the implementation. A pull request that trips a gate without a
prior decision will be asked to stop and discuss, regardless of quality.

**How approval is recorded.** The maintainer's decision is recorded in the place the
change lives: an ADR under [`docs/adr/`](docs/adr/) for a boundary or design decision, the
unit's `plan.md` / completion report under `specs/` for spec-driven work, and the issue or
pull-request thread in every case. A gate is not "passed" because a reviewer did not
object — it is passed when there is a written decision to point at.

## Where the truth lives

When two documents disagree, resolve the conflict in this order:

1. `.specify/memory/constitution.md` — the ten principles. The constitution wins over
   everything.
2. `docs/architecture/AI_HANDOFF_OPERATING_TEMPLATE.md` and
   `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` — the operational rules and the
   per-package boundaries.
3. `src/` + `tests/` + `pyproject.toml` — what the code actually does.
4. `docs/loopplane-agent-board.md` — the **only** authority on whether a unit is complete.
5. `docs/api-reference.md`, then `specs/`, then `docs/capabilities.md` /
   `docs/gap-analysis.md`, then `CHANGELOG.md`, then `README.md`.

Guides under `docs/guides/` are navigational: if one contradicts `docs/api-reference.md`
or `docs/capabilities.md`, the guide is wrong by definition.

## How changes are decided

- **Bug fixes and documentation** — open a pull request. No prior decision needed unless
  it trips a gate above.
- **New behavior** — open an issue first so the design can be agreed. Substantial work is
  specified first: a spec, a plan, and a task list under `specs/`, per Constitution I.
  Small changes do not need that ceremony; the maintainer will say when they do.
- **Architecture decisions** — recorded as an ADR under `docs/adr/`, numbered ascending,
  one decision per file, approved at the planning stage rather than after implementation.
- **Risks and known compromises** — tracked in `docs/architecture/RISK_REGISTER.md` and
  summarized for contributors in the hazard map in `CONTRIBUTING.md`.

## Review and merge

Every pull request must pass the four quality gates (`ruff format --check`, `ruff check`,
`mypy` strict, `pytest`) plus the repository's contract tests, and must keep runtime
behavior byte-identical unless the change is explicitly about changing behavior.
`.github/CODEOWNERS` automatically requests maintainer review for load-bearing paths;
those paths do not merge without it.

## Releases

Releases are maintainer-only, gated, and documented in
[`docs/release-process.md`](docs/release-process.md). Automation validates
tag/version/changelog synchronization and fails closed; it never decides to release.

## Security

Report vulnerabilities privately per [`SECURITY.md`](SECURITY.md) — never in a public
issue. The maintainer triages and coordinates disclosure.

## Code of conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). The maintainer is
responsible for enforcement.

## Changing this document

Governance changes are themselves maintainer decisions: open an issue proposing the
change. Changes to `.specify/memory/constitution.md` additionally follow the amendment and
versioning rules in the constitution's own Governance section.
