# Feature Specification: Notebook Editing (`notebook_edit`)

**Feature Branch**: `046-notebook-edit`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "A `notebook_edit` tool on the Internal Tool Adapter to edit Jupyter (`.ipynb`) cells within the working scope (insert / replace / delete a cell by index), reusing the stale-write guard pattern. Unit 046, Tier-1; closes gap G2. Additive, Gateway-only, no schema change, no ADR."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent edits a notebook cell (Priority: P1)

While working in a repository that contains Jupyter notebooks, the agent replaces the
source of a specific cell, inserts a new cell, or deletes a cell — without rewriting the
whole `.ipynb` by hand and without corrupting the notebook's JSON structure or its other
cells' outputs/metadata.

**Why this priority**: This is the core value — notebooks are a common artifact the
reference agent harnesses can edit (gap G2) and LoopPlane currently cannot; safe
cell-level edits let the agent work in notebook-based projects.

**Independent Test**: Read a small `.ipynb`, then call `notebook_edit` to replace a cell's
source; confirm only that cell changed and the notebook still parses as a valid notebook.

**Acceptance Scenarios**:

1. **Given** a notebook read in this session, **When** the agent replaces cell N's source,
   **Then** only cell N's source changes and the rest of the notebook (other cells,
   outputs, metadata, nbformat) is preserved and still valid.
2. **Given** a notebook, **When** the agent inserts a new cell (code or markdown) at index
   N, **Then** the new cell appears at N and existing cells shift down, structure intact.
3. **Given** a notebook, **When** the agent deletes cell N, **Then** that cell is removed
   and the remaining cells are preserved in order.

---

### User Story 2 - Safe, guarded edits (Priority: P2)

Edits are guarded the same way file edits are: the notebook must have been read in this
session and be unchanged since, and the target cell index must be valid — otherwise the
edit is rejected with a clear error and the file is left untouched.

**Why this priority**: Safety — prevents clobbering a notebook that changed underfoot or
an out-of-range edit, consistent with the existing `edit_file` stale-write guard.

**Independent Test**: Attempt a `notebook_edit` without a prior read, or with an
out-of-range index, or after the file changed since the read; confirm each is rejected
with a normalized error and the file is unchanged.

**Acceptance Scenarios**:

1. **Given** a notebook not read this session, **When** the agent edits it, **Then** the
   edit is rejected (stale-write guard) and the file is unchanged.
2. **Given** an out-of-range cell index, **When** the agent edits, **Then** a normalized
   error is returned and the file is unchanged.

---

### User Story 3 - Governed and scoped like every tool (Priority: P3)

`notebook_edit` is reachable only through the Tool Gateway, confined to the run's working
scope (no editing arbitrary host paths), and governed by the existing policy / plan-mode /
hook layers.

**Why this priority**: Consistency and safety — all file-touching tools share the same
scope confinement and governance.

**Independent Test**: A path outside the working scope is rejected; `describe()` advertises
`notebook_edit` as a non-read-only tool.

**Acceptance Scenarios**:

1. **Given** a path that resolves outside the working scope, **When** the agent calls
   `notebook_edit`, **Then** it is rejected with a normalized error and nothing is written.

---

### Edge Cases

- **Not a valid notebook** (malformed `.ipynb` JSON / missing `cells`): rejected with a
  clear normalized error; file unchanged.
- **Out-of-range index** (replace/delete beyond the last cell): rejected; file unchanged.
- **Insert at the end** (index == cell count): valid — appends.
- **Replace with an unchanged source**: allowed (a no-op write) or rejected as no-change —
  consistent with the file-edit conventions.
- **Path outside the working scope / not read this session / changed since read**: rejected
  (scope + stale-write guards); file unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `notebook_edit` tool, reachable only through the
  Tool Gateway (V), that edits a single cell of a Jupyter `.ipynb` notebook within the
  run's working scope.
- **FR-002**: The tool MUST support three operations on a cell selected by index: replace
  the cell's source, insert a new cell (with a cell type of `code` or `markdown`), and
  delete the cell.
- **FR-003**: An edit MUST preserve the rest of the notebook — other cells, their outputs
  and metadata, and the notebook's top-level `nbformat`/metadata — and MUST leave the file
  a valid notebook.
- **FR-004**: The tool MUST apply the existing stale-write guard: the notebook must have
  been read in this session and be unchanged since that read; otherwise the edit is
  rejected with a normalized error and the file is unchanged.
- **FR-005**: The tool MUST reject an out-of-range cell index, a malformed/non-notebook
  file, and a path outside the working scope with a clear normalized error, leaving the
  file unchanged.
- **FR-006**: On success the tool MUST report a concise confirmation (the operation and the
  affected cell) as its result.
- **FR-007**: Adding the tool MUST be additive: no change to the runtime event schema or
  `SCHEMA_VERSION`, the content model, or any existing tool; no new runtime dependency
  (Jupyter notebooks are JSON and parse with the standard library).

### Key Entities *(include if feature involves data)*

- **Notebook**: a Jupyter `.ipynb` document — JSON with an ordered `cells` list plus
  top-level `nbformat`/metadata.
- **Cell**: one entry in `cells` — a `cell_type` (`code`/`markdown`), a `source`, and
  (for code) `outputs`/`metadata` that an edit must preserve unless the cell is replaced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a replace/insert/delete, the notebook still parses as a valid notebook
  and only the targeted cell (and ordering) changed; other cells' outputs/metadata are
  byte-preserved.
- **SC-002**: 100% of guarded failures (no prior read, changed-since-read, out-of-range,
  malformed, out-of-scope) are rejected with the file unchanged.
- **SC-003**: Runs that do not call the tool are unaffected — the existing test suite passes
  unchanged and no event-schema or content-model change is introduced.

## Assumptions

- The direct "user" is the agent during a run; the beneficiary is anyone whose project
  contains notebooks the agent should edit.
- `.ipynb` is parsed and written as JSON with the standard library (no `nbformat`/Jupyter
  dependency); the tool preserves unknown fields by round-tripping the parsed document.
- The stale-write guard reuses the existing `edit_file`/`write_file` mechanism (a prior
  `read_file` of the notebook in the session).
- Cell selection is by integer index in this unit; selection by a notebook cell id is a
  possible later refinement.
- Out of scope: executing notebooks, managing kernels/outputs, creating a new notebook from
  scratch (use `write_file`), and any UI.
- Per Constitution IX, the concept is borrowed from the reference harnesses but re-derived.
