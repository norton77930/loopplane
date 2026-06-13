# Contract: Tool Gateway

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-020–FR-026, FR-030–FR-034,
FR-040–FR-045, FR-055 | **Date**: 2026-06-13

The single chokepoint for everything tool-related (constitution Principle V). The runtime
offers **no other path** by which a tool can be resolved, authorized, or executed (FR-020,
SC-002).

## Pipeline

Every call passes the same stages, in order:

| Stage | Semantics | On failure |
|---|---|---|
| 1. Resolve | Look up the call's tool name in the registry | `unknown-tool` error result (FR-021) |
| 2. Validate | Check input against the tool's declared JSON Schema; undeclared properties are rejected | `validation` error result, before any execution (FR-022) |
| 3. Decide | Obtain a policy decision per [approval.md](./approval.md); skill execution-profile constraints are honored here (FR-055) | `policy-denial` error result carrying the denial reason; the run continues (FR-023, FR-111) |
| 4. Execute | Invoke through the owning adapter; stream outputs; propagate cancellation | `execution` error result (FR-004, FR-032) |
| 5. Time-limit | Enforce the per-call execution time limit | `timeout` error result (FR-024) |
| 6. Normalize | Map every failure mode to the Normalized Error shape ([../data-model.md](../data-model.md)); raw adapter or internal errors never cross the boundary | — (FR-025) |
| 7. Size-manage | Oversized results are reduced for the model; where artifact storage applies, the full output is preserved with an in-result reference per [artifacts.md](./artifacts.md) | — (FR-026, FR-090–FR-091) |

Failure at any stage produces an error-marked Tool Result; **no stage failure ends the
run**.

## Registry

- Tools register with a Tool Descriptor ([../data-model.md](../data-model.md)): name,
  description, input schema, `concurrency_safe` and `read_only` flags (both defaulting to
  the conservative `false`, FR-031), and source.
- External tools register under source-qualified names so they cannot collide with internal
  tools or with other servers' tools (FR-042).
- The registry answers the Agent Loop's partitioning question: which of a turn's calls are
  declared concurrency-safe (FR-005).

## Adapter SPI

An adapter (tool source) provides exactly three capabilities:

1. **describe** — yield the Tool Descriptors it currently offers;
2. **invoke** — execute one validated call, yielding a stream of text/image/error outputs
   (an error output marks the call failed while the run stays alive, FR-030, FR-032);
3. **shutdown** — release resources cleanly.

Adapters never see policy, timeouts, size management, or event emission — those belong to
the Gateway.

### Internal Tool Adapter obligations

- Ships the baseline tool set: file reading, file writing/editing, content search, command
  execution, and asking the user a question — each reachable only through the Gateway
  (FR-033).
- File-modifying tools enforce the stale-write guard: editing or overwriting an existing
  file requires a fresh same-session read; otherwise the call fails as a `validation`-class
  error. New-file creation is exempt (FR-034).

### MCP Tool Adapter obligations

- Loads server definitions from layered configuration where more specific scopes override
  broader ones; a malformed entry disables only itself with a diagnostic (FR-040).
- Manages each server's lifecycle: connect, discover, invoke, clean shutdown (FR-041).
- Translates external schemas into the runtime's validation model with a safe permissive
  fallback for untranslatable constructs (FR-044).
- Isolates failure per server: one server failing to connect or invoke leaves all other
  tools available, reported as a `diagnostic` event (FR-043).
- Subjects every external tool to stages 1–7 above, identically to internal tools (FR-045).

## Invariants

- 100% of executions traverse this pipeline (SC-002); the Gateway is the only component
  allowed to call adapter `invoke`.
- Policy denials are **not** execution failures: they carry their own error category and
  are excluded from execution-failure metrics (FR-104).
- The Gateway emits `tool-call-started` / `tool-call-completed` events per
  [runtime-events.md](./runtime-events.md); adapters emit nothing.
