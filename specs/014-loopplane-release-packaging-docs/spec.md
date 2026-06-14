# Feature Specification: LoopPlane Release Packaging & Docs

**Feature Branch**: `014-loopplane-release-packaging-docs`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Release Packaging & Docs (unit 014) — the capstone release-quality unit
on top of the completed roadmap (001 runtime foundation, 002 host interface, and the additive layers
003–013). Bring the project to public release quality WITHOUT changing any runtime behavior or any
established public contract: packaging metadata, a single-source version, a PEP 561 `py.typed` marker,
a public API reference, a getting-started quickstart, an examples index, a docs index, a changelog, a
public project README, a public-safe final audit, and CI readiness. Additive and strictly non-breaking;
no new runtime dependency. Deterministic, public-safe, offline, English. Publishing/upload, signed
releases, a hosted docs site, release automation, multi-distribution packaging, and docstring-based API
generation are reserved extension points."

## User Scenarios & Testing *(mandatory)*

Release Packaging & Docs is the **capstone** unit: it makes the already-built roadmap (the Phase-1
runtime foundation, the Host Interface, and the eleven additive layers 003–013) **installable,
discoverable, and release-ready** — without adding a feature or touching a public contract. Every story
is a packaging / documentation / verification artifact over the existing tree; the only code additions
are a single-source version constant and a `py.typed` marker. Nothing here changes runtime behavior.

### User Story 1 - A buildable, installable, typed distribution (Priority: P1)

A maintainer builds a source distribution and a wheel from the committed tree, offline, and installs
the `loopplane` package: every subpackage imports, the package is recognized as **typed** (it ships a
PEP 561 marker), and it reports a **single-source** version (`loopplane.__version__` consistent with the
installed distribution metadata, with no duplicated literal that can drift). This is the minimum viable
release artifact: a package others can install and type-check against.

**Why this priority**: An installable, typed, correctly-versioned distribution is the foundation of a
release; the docs, API reference, and CI all describe or verify this artifact.

**Independent Test**: Assert the packaging metadata is complete and internally consistent, that
`loopplane.__version__` equals the distribution's declared version (single source), that the `py.typed`
marker is present and shipped as package data, and that every `loopplane` subpackage is importable.

**Acceptance Scenarios**:

1. **Given** the committed tree, **When** a maintainer builds the distribution offline, **Then** a
   source distribution and a wheel are produced with no new runtime dependency and with the existing
   optional extras preserved.
2. **Given** the installed package, **When** its version is read from the distribution metadata and from
   `loopplane.__version__`, **Then** the two are identical (a single source of truth, no drift).
3. **Given** a downstream type-checker, **When** it resolves `loopplane`, **Then** the package is seen as
   typed because it ships a PEP 561 `py.typed` marker.

### User Story 2 - A public API reference that cannot drift (Priority: P2)

A new adopter reads a single **public API reference** that enumerates every shipped layer's public
surface — the public names plus a one-line description each — derived from each package's declared
exports, so they can find what to import without reading source. The reference is checked against the
code so it can never silently drift.

**Why this priority**: A trustworthy, drift-proof map of the public surface is the highest-value
documentation artifact for adopters and the clearest signal that the surface is stable.

**Independent Test**: Assert the API reference represents every shipped layer and that every public name
it lists exists in the corresponding package's public exports (`__all__`), and vice versa where required
— a mismatch between the reference and the code fails the test.

**Acceptance Scenarios**:

1. **Given** the shipped layers, **When** the API reference is built, **Then** it lists every layer and,
   for each, its public names with a one-line description.
2. **Given** the API reference, **When** it is checked against the code, **Then** every listed public
   name exists in that package's public exports and every shipped layer is represented (no drift).
3. **Given** any reference entry, **When** it is read, **Then** it surfaces a public name and description
   only — never private internals, source, secrets, or private references.

### User Story 3 - A navigable getting-started surface (Priority: P3)

A new adopter lands on a release-quality **README**, follows a single **getting-started** guide to
install the package and run the smallest end-to-end example, and uses a **docs index** and an
**examples index** to reach every per-layer guide and runnable example. The indexes stay consistent with
the files that actually ship.

**Why this priority**: Discoverable navigation turns an installable package into an adoptable one; it
builds directly on the API reference (US2).

**Independent Test**: Assert the README links the quickstart and the docs; the docs index links every
per-layer guide present under `docs/`; the examples index lists every runnable example under `examples/`
with a one-line description and run command; and there is no missing or dangling entry in either index.

**Acceptance Scenarios**:

1. **Given** the project, **When** an adopter reads the README, **Then** it provides an overview, install
   instructions, a quickstart link, a layer map, links to the docs, and the license reference.
2. **Given** the `docs/` guides and `examples/` quickstarts, **When** the docs index and examples index
   are built, **Then** each lists exactly the files present — every guide/example is linked and no entry
   points at a missing file.
3. **Given** the getting-started guide, **When** an adopter follows it, **Then** it installs the package,
   runs the smallest end-to-end example, and links out to each layer's guide and example.

### User Story 4 - Reproducible quality gates in CI (Priority: P4)

A contributor (and the continuous-integration system) runs the project's **canonical quality gates** —
format check, lint, strict type-check, and the full test suite — deterministically and offline. The CI
definition encodes exactly the gates that pass locally, and the local commands are documented.

**Why this priority**: Encoded, reproducible gates are what keep the released artifact green over time;
they protect every prior unit's work.

**Independent Test**: Assert the CI definition runs the four canonical gates (format check, lint, strict
type-check, full tests) on the supported Python version with no secret, and that the same gate commands
are documented for local use.

**Acceptance Scenarios**:

1. **Given** the repository, **When** CI runs, **Then** it executes the format check, the lint, the
   strict type-check, and the full test suite on the supported Python version, offline and without any
   secret.
2. **Given** a contributor's machine, **When** they run the documented gate commands locally, **Then**
   the gates are the same ones CI runs and produce the same pass/fail outcome.
3. **Given** a change that breaks a gate, **When** CI runs, **Then** the corresponding gate fails
   explicitly (no silent pass).

### User Story 5 - Release-readiness: public-safe audit and changelog (Priority: P5)

A maintainer confirms the repository is ready to release: a **repository-wide public-safety audit**
reports no secret, private path, internal name, internal IP, or token anywhere in the committed tree; a
**release-readiness checklist** enumerates the gates that must pass; and a public-safe **changelog**
summarizes the released layers (units 001–013) at a high level.

**Why this priority**: The final audit and the release history are the last gate before a public
release; they guard everything the other stories produce.

**Independent Test**: Assert the public-safety audit covers the whole committed tree and reports zero
findings; the release-readiness checklist enumerates the required gates; and the changelog follows a
recognized changelog structure, covers the released layers, and contains no private reference.

**Acceptance Scenarios**:

1. **Given** the committed tree, **When** the public-safety audit runs, **Then** it scans every committed
   file and reports an explicit, listed result — an empty finding set is the passing state.
2. **Given** the release-readiness checklist, **When** a maintainer reviews it, **Then** it lists the
   gates that must pass before release (build succeeds, gates green, public-safety clean, a license file
   present, changelog current).
3. **Given** the changelog, **When** it is read, **Then** it summarizes the released layers (001–013) at
   a high level in a recognized structure, with no private reference, internal name, path, or secret.

### Edge Cases

- **Version drift**: if the version constant and the packaging metadata disagree, the consistency check
  fails — there is exactly one source of truth.
- **API-reference drift**: if the reference lists a public name that no longer exists (or omits a shipped
  layer), the consistency check fails rather than silently misleading adopters.
- **Index drift**: a guide or example present on disk but missing from its index — or an index entry
  pointing at a missing file — fails the index-consistency check.
- **Missing license**: the packaging and README reference a `LICENSE` file; if it is absent, the build
  still proceeds but the release-readiness checklist marks the license gate incomplete (the specific
  license is a maintainer decision, not chosen by this unit).
- **Public-safety finding**: any secret / private path / internal name / IP / token found anywhere in
  the committed tree is an explicit, listed failure — never a silent pass.
- **No new dependency**: adding a runtime dependency, or modifying an established public contract, is out
  of bounds for this unit and would fail its non-breaking guarantee.

## Requirements *(mandatory)*

### Functional Requirements

**Packaging, versioning & typing (US1)**

- **FR-001**: The packaging metadata MUST be complete for a public distribution — name, version,
  description, readme, license reference, authors, classifiers, keywords, Python requirement, and project
  URLs — and MUST discover the `loopplane` package and all of its subpackages.
- **FR-002**: The release version MUST have a single source of truth, exposed as `loopplane.__version__`,
  with the packaging metadata deriving from it (no duplicated version literal that can drift).
- **FR-003**: The distribution MUST ship the package's type information — a PEP 561 `py.typed` marker
  included as package data — so downstream type-checkers treat `loopplane` as typed.
- **FR-004**: A source distribution and a wheel MUST be buildable from the committed tree offline, adding
  no new runtime dependency and preserving the existing optional extras.

**Public API reference (US2)**

- **FR-010**: A public API reference MUST enumerate every shipped layer's public surface as its public
  names plus a one-line description each, derived from each package's declared public exports.
- **FR-011**: The API reference MUST stay consistent with the code: every public name it lists MUST exist
  in the corresponding package's public exports, and every shipped layer MUST be represented — a drift
  between the reference and the code is a failure.
- **FR-012**: The API reference MUST surface public names and descriptions only — never private
  internals, source, secrets, or private references.

**Getting-started navigation (US3)**

- **FR-020**: A public-facing project README MUST provide an overview, install instructions, a quickstart
  link, a layer map, links to the docs, and the license reference.
- **FR-021**: A single getting-started guide MUST show how to install the package, run the smallest
  end-to-end example, and reach each layer's existing guide and example.
- **FR-022**: A docs index MUST link every per-layer guide present under `docs/`, and an examples index
  MUST list every runnable example under `examples/` with a one-line description and run command; both
  MUST stay consistent with the files present (no missing or dangling entry).

**Quality gates & CI (US4)**

- **FR-030**: A continuous-integration definition MUST run the project's canonical quality gates — format
  check, lint, strict type-check, and the full test suite — on the supported Python version,
  deterministically and offline, with no secret.
- **FR-031**: The same gates MUST be runnable locally, and the gate commands MUST be documented.

**Release-readiness: audit & changelog (US5)**

- **FR-040**: A repository-wide public-safety audit MUST confirm that no secret, private path, internal
  name, internal IP, or token is committed anywhere in the tree; any finding MUST be listed explicitly,
  and an empty finding set is the passing state.
- **FR-041**: A release-readiness checklist MUST enumerate the gates that must pass before release — the
  distribution builds, the quality gates are green, the public-safety audit is clean, a license file is
  present, and the changelog is current.
- **FR-042**: A public-safe changelog MUST summarize the released layers (units 001–013) at a high level
  in a recognized changelog structure, with no private reference, internal name, path, or secret.

### Non-Functional Requirements

- **NFR-001 (Non-breaking)**: This unit MUST NOT modify, rewrite, or re-shape any established public
  contract (the 001/002 contracts or any layer's public surface) and MUST NOT change runtime behavior.
  The only code-level additions are the single-source version constant and the `py.typed` marker.
- **NFR-002 (No new runtime dependency)**: This unit MUST NOT add a runtime dependency; build and CI
  tooling use development/build tooling only.
- **NFR-003 (Determinism / reproducibility / offline)**: Every artifact — the build, the docs, the API
  reference, the changelog, and the CI definition — MUST be reproducible from the committed tree with no
  network access and no environment-specific configuration.
- **NFR-004 (Public-safe / English)**: Every committed artifact MUST be public-safe (no secrets, private
  paths, internal names, or IPs) and English.
- **NFR-005 (Testable)**: The packaging consistency, the API-reference / docs / examples consistency, the
  public-safety audit, and the changelog structure MUST be verified by in-process tests; the gates run
  offline.

### Key Entities *(include if data involved)*

- **Distribution**: the buildable source distribution and wheel produced from the committed tree.
- **Version source**: the single source of truth for the release version, exposed as
  `loopplane.__version__` and reflected in the packaging metadata.
- **Type marker**: the PEP 561 `py.typed` marker shipped as package data.
- **API reference**: the metadata-only enumeration of every shipped layer's public names + descriptions.
- **README / getting-started guide**: the public-facing entry points for a new adopter.
- **Docs index / examples index**: catalogs of the per-layer guides and runnable examples.
- **CI definition**: the encoded, reproducible quality gates.
- **Public-safety audit / release-readiness checklist**: the final pre-release verification artifacts.
- **Changelog**: the public-safe, high-level release history of the shipped layers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can build an installable distribution from the committed tree offline; the
  installed package reports a single version identical to `loopplane.__version__` and is recognized as
  typed (ships `py.typed`).
- **SC-002**: A new adopter can find every shipped layer's public surface and a runnable starting point
  from the README, the API reference, and the indexes, with 0 references that do not match the code (no
  drift) and every shipped layer represented.
- **SC-003**: The canonical quality gates (format, lint, strict type-check, full tests) pass and are
  encoded identically in CI and in the documented local commands.
- **SC-004**: The repository-wide public-safety audit reports 0 findings across the entire committed
  tree.
- **SC-005**: The docs index, the examples index, and the changelog cover 100% of the released
  guides / examples / layers with 0 missing or dangling entries.
- **SC-006**: 0 established public contracts are modified and 0 new runtime dependencies are added — the
  unit is strictly additive (version constant + `py.typed` marker only).

## Assumptions

- The project **already** declares a build backend (hatchling), a version literal, a minimal README, and
  a CI workflow that runs the four gates; this unit **completes and hardens** these rather than creating
  them from scratch.
- The version is **currently duplicated** (the packaging metadata and `loopplane.__version__` both carry
  a literal); this unit consolidates them to a single source of truth.
- **License selection is a maintainer / legal decision and is NOT made by this unit.** The packaging and
  README reference a `LICENSE` file, and "a `LICENSE` file is present" is a release-readiness checklist
  gate. If the file is absent the build still proceeds, but the checklist marks the license gate
  incomplete. The unit does not pick or author a software license.
- The **supported Python version** is the project minimum (3.12+); the CI gates target it on the existing
  OS matrix. Extending the version/OS matrix is optional and out of this unit's required scope.
- **No new runtime dependency** is added; the build frontend and CI use development/build tooling only
  (the existing dev tooling — ruff, mypy, pytest — plus a standard build frontend invoked offline).
- The API reference, docs index, and examples index are **derived from what already ships** (each
  package's public exports, the `docs/*.md` guides, the `examples/*.py` quickstarts); this unit adds no
  new product behavior and no new example that introduces behavior.
- This unit ships packaging metadata, the version consolidation, the `py.typed` marker, the API
  reference, the README, the getting-started guide, the docs/examples indexes, the changelog, the
  release-readiness checklist, the public-safety audit coverage, the CI verification, and in-process
  consistency tests — and nothing else.

### Reserved extension points (named, not built)

- Publishing or uploading to any public package index (for example a PyPI release).
- Cryptographically signed releases or build attestations.
- A hosted documentation website or an automated documentation-generation pipeline.
- Automated version bumping or release automation.
- Multi-distribution packaging (for example conda or OS-level packages).
- Auto-generating the API reference from docstrings via an external tool.
