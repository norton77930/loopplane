# Implementation Plan: Code Review Remediation

**Branch**: `main` (Spec Kit feature artifact:
`073-code-review-remediation`) | **Date**: 2026-06-23 |
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from
`specs/073-code-review-remediation/spec.md`

## Summary

Close the concrete defects and risks recorded in
`docs/code-review-001-072.md`: restore reliable locked dependency sync and
desktop gates, repair desktop/web drift, expand CI coverage, sanitize
model-visible MCP and web-fetch errors, bound web-fetch response retention,
make Spec Kit task audit state explicit, and complete lower-priority frontend
and Electron hardening follow-ups. The work is implemented as a remediation
unit rather than new product scope.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript/React 19 app code, Electron
desktop shell, GitHub Actions workflows.

**Primary Dependencies**: Existing LoopPlane runtime, FastAPI/web API host,
React/Vite/Vitest web frontend, Electron/Vitest desktop package, uv lockfile.
No new runtime framework dependency is planned.

**Storage**: Existing repository files only. No new persistent service or
database storage.

**Testing**: pytest, ruff, mypy, uv locked sync, Vitest, TypeScript
typechecks, Vite build, GitHub Actions path inspection, public-safety scans.

**Target Platform**: Python library/runtime, web frontend, desktop shell, and
repository CI.

**Project Type**: Multi-surface runtime repository with Python, web frontend,
desktop shell, CI, and Spec Kit docs.

**Performance Goals**: Web fetch must bound model-visible/cached response
content at the adapter boundary before Gateway truncation. Bundle-size warning
is a low-priority follow-up unless a small, scoped split is available.

**Constraints**: Preserve public contracts unless a finding requires a tested
adjustment; do not touch `openspec/`; do not copy private reference material;
do not hand-edit Spec Kit managed AGENTS blocks; keep remediation traceable to
073 tasks; prefer minimal fixes over broad rewrites.

**Scale/Scope**: One remediation unit covering findings from 001-072 review.
P0/P1 findings are blocking; P2/P3 findings remain in scope but can be
completed after core gates are restored.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Result |
| --------- | ----------- |
| I. Spec-First Development | PASS - this 073 spec, plan, and tasks trace every code change to review findings. |
| II. Greenfield Implementation | PASS - no legacy/private implementation copy is required. |
| IV. Runtime Boundary Clarity | PASS - tool error normalization remains inside adapters/tool surfaces; CI/frontend fixes do not blur runtime ownership. |
| V. Tool Gateway Ownership | PASS - MCP and web-fetch fixes normalize adapter/tool outputs without moving tool resolution or authorization. |
| VI. Runtime Event Bus Ownership | PASS - no event schema, content block, termination reason, or schema-version change is planned. |
| VII. Public-Safe Documentation | PASS - artifacts use public-safe paths and generic secret examples only; `openspec/` remains untouched. |
| VIII. No SDK Replacement | PASS - no agent framework replacement or new runtime SDK dependency. |
| X. Testable Evolution | PASS - each remediation story includes tests or concrete verification commands plus rollback guidance. |

## Project Structure

### Documentation (this feature)

```text
specs/073-code-review-remediation/
├── spec.md
├── checklists/
│   └── requirements.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── remediation-contract.md
└── tasks.md

docs/
├── code-review-001-072.md
└── spec-task-audit-exceptions.md
```

### Source Code (repository root)

```text
.github/workflows/
├── ci.yml
└── desktop.yml

uv.lock

src/loopplane/
├── adapters/mcp/adapter.py
└── tools/web.py

tests/
├── contract/
│   └── test_spec_task_audit.py
└── unit/
    ├── test_mcp_adapter.py
    └── test_web_tools.py

apps/web/
└── src/__tests__/AppRoot.test.tsx

apps/desktop/
├── electron/main.ts
├── src/App.tsx
└── src/__tests__/App.test.tsx
```

**Structure Decision**: Keep the remediation surgical. Fix each finding at the
surface where it was observed, add regression coverage next to existing tests,
and document audit exceptions rather than rewriting historical task files
without evidence.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0 Research

See [research.md](./research.md).

Key decisions:

- Treat stale `uv.lock` and desktop/web drift as blocking P0 fixes before
  broader security and audit remediation.
- Repair the desktop shell against current web state/components instead of
  restoring deleted web components.
- Add `apps/web/**` to desktop workflow path triggers because desktop imports
  web source directly.
- Normalize model-visible errors at the adapter/tool boundary with fixed,
  class-specific messages; keep detailed diagnostics out of returned content.
- Bound web-fetch body handling before cache reuse. The initial implementation
  can use a deterministic character/byte cap around injected fetcher output;
  streaming can be a later optimization if current fetcher contract cannot
  stream.
- Reconcile historical Spec Kit task drift through an explicit audit and
  durable exception file, not by mass-checking old tasks.

## Phase 1 Design

See:

- [data-model.md](./data-model.md)
- [contracts/remediation-contract.md](./contracts/remediation-contract.md)
- [quickstart.md](./quickstart.md)

Post-design Constitution re-check: PASS. The design remains remediation-only,
testable, public-safe, and does not alter runtime event or Tool Gateway
ownership contracts.

## Agent Context Update

`.specify/extensions.yml` registers optional `agent-context` hooks after
specify and plan. This plan does not hand-edit the Spec Kit managed
`AGENTS.md` block. If the optional hook still hits the known PowerShell YAML
fallback issue, record that result in final review instead of editing the
managed block manually.
