# Contract: Model Boundary

**Feature**: [../spec.md](../spec.md) | **Disposition**: Minimal contract only
(reference-analysis §3) | **Date**: 2026-06-13

The seam through which the Agent Loop drives a model. Deliberately minimal: provider
integrations are not a phase-1 deliverable; this contract exists so the loop has exactly
one model-facing interface and so tests can substitute it completely.

## Request

One model turn receives:

| Input | Notes |
|---|---|
| assembled context | History blocks plus assembly-time augmentations (memory, skill listings) — the durable history itself stays verbatim (FR-073) |
| tool descriptors | The Gateway-registered tools the model may request |
| limits | Generation limits the host configured |

## Response stream

The boundary yields a normalized stream, in order:

| Increment | Notes |
|---|---|
| text fragment | Surfaces as `assistant-output-increment` |
| reasoning fragment | Surfaces as `assistant-reasoning-increment`, when the model exposes reasoning |
| tool-call request(s) | call identity, tool name, raw input (validated later by the Gateway) |
| turn end | stop reason + token usage (input, output, cached, reasoning) — feeds `turn-completed` (FR-102) |

## Capabilities

The boundary answers one query: **context capacity** (the token budget the assembled
context must fit). Compaction (FR-008) consumes this; the runtime never hard-codes model
limits.

## Error modes

| Mode | Contract |
|---|---|
| context overflow | Signaled distinctly, so the loop can compact and retry exactly once before surfacing the failure (FR-008) |
| cancellation | Honored mid-stream without raising to the caller (FR-003) |
| other failures | Surface to the loop, which terminates the run with reason `unrecoverable-error` after its handling (FR-001) |

## Scripted substitute (research R7)

A test substitute implements this same contract from a declarative script of turns (text,
reasoning, tool requests, overflow signals, failures) and MUST be indistinguishable from a
real model to the loop. The substitute is the basis of golden event-sequence testing
(NFR-001) and of every automated acceptance scenario in the spec; at least one real model
integration is validated separately (spec Assumptions).
