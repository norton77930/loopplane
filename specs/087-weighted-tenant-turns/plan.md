# Implementation Plan: Weighted Tenant Turns

**Branch**: existing `086-cluster-fair-turn` | **Date**: 2026-09-07
**Spec**: [spec.md](spec.md)
**Input**: `specs/087-weighted-tenant-turns/spec.md`

## Summary

Add explicitly selected weighted fairness and permit stores. Share a deterministic
smooth weighted round-robin selector across memory and Postgres. Group requests by
tenant, retain FIFO within each group, and respect hard active/consecutive caps.
Use a new `WeightedPlatformFairness` composition over public `PlatformFairness`
for admission, plus a cancellation-safe local guard retaining 072 FIFO/consecutive
selection. Acquire shared weighted permits before local turns
so local queues cannot hide ready tenants. Existing 072/086 code paths stay intact.

## Technical Context

**Language/Version**: Python 3.12+.
**Primary Dependencies**: existing anyio; optional existing psycopg. No additions.
**Storage**: process memory or one dedicated Postgres coordination-state row.
**Testing**: pytest, deterministic state-machine properties, anyio scenarios and
offline transactional SQL stub; existing 072/085/086 regressions.
**Target Platform**: embedding library and multi-worker web/API hosts.
**Project Type**: runtime library; no transport/UI change.
**Performance Goals**: O(ready tenants + queued requests) selection, no score changes
on full-cap polling; one serialized transaction per durable state operation.
**Constraints**: default identity; base-dependency import boundaries; hard caps;
typed acquisition-only degradation; shielded cancellation cleanup; public-safe errors.
**Scale/Scope**: bounded integer weights 1..100; existing operator-set outstanding
caps bound each tenant's queued work. SQL snapshot serialization is a modest-cluster
implementation, not a high-throughput distributed queue promise.

## Constitution Check

Pre-research and post-design: PASS.

- I: spec, plan, tasks and analysis precede implementation; user authorized 087.
- II/IX: fresh code from local contracts, no private reference material.
- III/IV: fairness owns ephemeral model-start selection in Phase 1; stores injected.
- V/VI: no Gateway, Event Bus, checkpoint, termination or outward-contract change.
- VII: redacted representations/messages; public-safe artifacts and scans.
- VIII: no framework substitution or new dependency.
- X: focused RED before implementation; regression tests and rollback below.

§E assessment: no existing default, dependency/extra, event/checkpoint schema,
Gateway SPI/stage, HTTP contract or release is changed. New Postgres coordination
tables are ephemeral permit state under ADR 0021 D6, not session persistence.
No new boundary is introduced or blurred; this additive policy implementation
does not require amending the accepted 086 ADR. Its weighted-tier deferral is
addressed by this newly authorized unit, never by rewriting 086 artifacts.

## Project Structure

### Documentation (this feature)

`spec.md`, `checklists/requirements.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/weighted-turns.md`, `quickstart.md`, `tasks.md`,
`implementation-evidence.md`.

The read-only analyze report is recorded in implementation evidence; no separate
analysis artifact is required by the analyze skill.

### Source Code (repository root)

- `src/loopplane/fairness_weighted.py`: public policy, protocol, memory store and
  fairness composition; internal deterministic queue/score helpers.
- `src/loopplane/fairness_weighted_postgres.py`: lazy psycopg implementation with
  dedicated state, serialized read/modify/write and config agreement.
- `tests/unit/test_weighted_tenant_turns.py`: share/cap/FIFO/state/lifecycle properties.
- `tests/unit/test_weighted_tenant_postgres.py`: durable contract and outage checks.
- `tests/weighted_pg_stub.py`: isolated transactional offline store fixture.
- `tests/contract/test_import_matrix.py`: register only the two new Phase-1 edges.
- `tests/unit/test_webapi_admission.py`: weighted opt-in admission regression.
- `docs/api-reference.md`, `docs/capabilities.md`, `docs/gap-analysis.md`, board:
  additive documentation and accurate completion evidence.

No top-level re-export, no edits to frozen 086 artifacts. No release metadata change.
Agent context is refreshed through the Spec Kit extension.

## Complexity Tracking

No constitution exception. Two explicit tradeoffs: safety caps can suppress requested
ratios; a coordinator outage falls back to local equal fairness, losing cluster
capacity/weighted guarantees exactly as documented in the spec. New weighted state
is isolated from 086 state, so mixed-mode workers are separate scheduling domains
and MUST NOT be presented as one coordinated deployment.

## Rollback

Stop/drain the worker group and restore construction with existing `PlatformFairness`.
Leave the new ephemeral table unused; do not delete user data as part of rollback.
No checkpoint migration or old-table rewrite is necessary. Uncommitted code can be
reviewed by scoped diff; no commit, branch or deployment is authorized in this run.
