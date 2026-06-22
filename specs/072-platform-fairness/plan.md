# Implementation Plan: Platform Fairness

**Branch**: `main` (Spec Kit feature artifact: `072-platform-fairness`) | **Date**:
2026-06-22 | **Spec**:
[spec.md](./spec.md)

**Input**: Feature specification from `specs/072-platform-fairness/spec.md`

## Summary

Add an opt-in, in-process platform fairness layer for multi-tenant model-call
work. The design keeps unit 061's per-principal host pool and each host's
sequential invariant intact, while adding a shared fairness collaborator that
can reject over-quota tenant work before admission and fairly gate model-call
starts across tenants inside the Agent Loop. Distributed fairness,
cross-process coordination, external queues, many-writer durability, runtime
event vocabulary changes, content block changes, and termination-reason changes
remain out of scope.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: anyio, FastAPI web/API host, existing LoopPlane
runtime/host/controller/model boundaries. No new runtime dependency.

**Storage**: In-memory only for this unit. No database, durable queue, or
cross-process state.

**Testing**: pytest plus existing ruff, ruff format, mypy gates.

**Target Platform**: Python library and optional FastAPI web/API host.

**Project Type**: Library/runtime with web/API integration.

**Performance Goals**: Under deterministic two-tenant tests, a within-quota
tenant with pending work starts within one fair scheduling cycle and no tenant
receives more than the configured fairness window of consecutive starts while
another tenant is ready.

**Constraints**: Default-off byte-identical behavior; public-safe quota
rejections; no Tool Gateway ownership change; no Runtime Event Bus schema
change; no termination-reason or content schema change; no private reference
material.

**Scale/Scope**: Single-process, in-memory fairness for hosts created in the
same process. Distributed platform fairness and many-writer durability are
deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Result |
| --------- | ----------- |
| I. Spec-First Development | PASS - 072 has spec, checklist, this plan, and ADR 0013. Implementation will wait for tasks. |
| IV. Runtime Boundary Clarity | PASS - fairness is a host/controller/loop collaborator with explicit admission and model-turn permit boundaries. |
| V. Tool Gateway Ownership | PASS - no tool resolution, authorization, execution, timeout, or artifact extraction changes. |
| VI. Runtime Event Bus Ownership | PASS - no new runtime event types, schema version change, content block shape, or termination reason. |
| VII. Public-Safe Documentation | PASS - no private paths, credentials, raw internal names, or private reference material in plan artifacts. |
| X. Testable Evolution | PASS - deterministic fairness, quota, default-off, cancellation, and public-safety tests are required. |

## Project Structure

### Documentation (this feature)

```text
specs/072-platform-fairness/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── platform-fairness.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)

docs/adr/
└── 0013-platform-fairness.md
```

### Source Code (repository root)

```text
src/loopplane/
├── fairness.py                    # New in-process fairness policy, quota, permit gate
├── context.py                     # Stamp tenant/principal identity into RunContext
├── loop/loop.py                   # Gate model-call starts before ModelBoundary.stream_turn
├── controller/controller.py       # Thread principal/fairness into RunContext and AgentLoop
├── host/
│   ├── config.py                  # RuntimeConfig opt-in fairness configuration
│   ├── assembly.py                # Wire fairness into RuntimeController
│   └── __init__.py                # Public exports if needed
└── webapi/
    ├── app.py                     # Map fairness admission rejection to public-safe 429
    ├── pool.py                    # Compose fairness above TenantHostPool where needed
    └── streaming.py               # Preserve public-safe SSE error handling

tests/
├── contract/
│   └── test_host_config.py        # Config validation/default-off coverage
└── unit/
    ├── test_platform_fairness.py  # Scheduler/quota/cancellation unit tests
    ├── test_loop_core.py          # AgentLoop fairness permit regression
    ├── test_tenant_host_pool.py   # Default-off / pool regression coverage
    └── test_webapi.py             # Public-safe 429 integration coverage as needed
```

**Structure Decision**: Use a single foundational `loopplane.fairness` module
instead of a web-only scheduler. The fairness gate must be shared by hosts in
the same process and consulted by the Agent Loop immediately before model calls,
while web/API admission maps quota rejection to HTTP 429 before work starts.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0 Research

See [research.md](./research.md).

Key decisions:

- Gate model-call starts in `AgentLoop` rather than only at web/API route
  boundaries, because fairness is about model-call access, not just HTTP run
  submission.
- Keep quota admission separate from model-call scheduling, so over-quota web
  requests can fail before a run starts without inventing a new termination
  reason.
- Use one in-process, host-supplied shared fairness collaborator across the
  tenant host pool. No durable queue, external broker, database coordination, or
  cross-process fairness.
- Materialize ADR 0013 because the roadmap board pre-settled the boundary but
  the ADR file was absent.

## Phase 1 Design

See:

- [data-model.md](./data-model.md)
- [contracts/platform-fairness.md](./contracts/platform-fairness.md)
- [quickstart.md](./quickstart.md)
- [ADR 0013](../../docs/adr/0013-platform-fairness.md)

Post-design Constitution re-check: PASS. The design remains default-off,
in-process, public-safe, testable, and does not alter Tool Gateway ownership,
Runtime Event Bus schema, content blocks, or termination reasons.

## Agent Context Update

Attempted execution:

```powershell
.specify/extensions/agent-context/scripts/powershell/update-agent-context.ps1 specs/072-platform-fairness/plan.md
```

Result: the hook exited without updating context because it could not parse
`.specify/extensions/agent-context/agent-context-config.yml`; the script emitted
the known PowerShell YAML fallback `SyntaxError: '(' was never closed`. The
Spec Kit managed block in `AGENTS.md` was not manually edited.
