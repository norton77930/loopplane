# Phase 0 Research: Cluster Fair Turn

All findings below were verified against this working tree on 2026-09-03. Nothing here
is inferred from documentation alone.

## R1 — 072 turn scheduling is process-local

`src/loopplane/fairness.py` `PlatformFairness._wake_waiters_locked` pops from an
in-process `_waiters` list, bounded by `max_active_model_calls` and
`max_consecutive_starts`. `model_turn` is the only public entry (`PlatformFairnessGate`).

Two workers therefore have two waiter lists. 085 cluster-scopes *admission* and
outstanding-work; it does not share this list (ADR 0020 D4 / 085 FR-016).

**Decision**: 086 cluster-scopes the *turn policy* (`max_active_model_calls` /
`max_consecutive_starts`) via an injected permit store. Local 072 remains defense
in depth.

## R2 — Mechanism fork (spec FR-018)

| Fork | What it is | Verdict |
| ---- | ---------- | ------- |
| **A** injectable permit collaborator on `PlatformFairness` | Loop still calls `model_turn`; cluster permit wraps the granted local turn | **Chosen** (ADR 0021 D1, Proposed) |
| **B** count starts only in webapi | Serving layer cannot see `AgentLoop` model turns | Rejected as sole mechanism |
| **C** new queue/lock extra | External product | GATE-§E; rejected |

**Alternative considered**: import 085 `AdmissionStore` from fairness. Rejected —
Phase-1 MUST NOT import webapi (spec FR-020, TARGET §1).

## R3 — Where the seam lives

`AgentLoop` already calls `fairness.model_turn` (`src/loopplane/loop/loop.py`).
`PlatformFairness` is supplied on `RuntimeConfig.platform_fairness`. Embedders who
want cluster turns construct the fairness object with a collaborator; `create_app`
does **not** grow a new argument (G5: no new defaulted serving knob).

Postgres implementation, if any, lives beside 085's store (webapi or a small
`loopplane.fairness` postgres module that lazy-imports psycopg). Fairness core
imports only the Protocol.

**Decision**: constructor injection on `PlatformFairness`, not `create_app(admission=)`
style. Tests share one in-memory store across two `PlatformFairness` instances.

## R4 — Failure polarity differs from 085

085 fail-closes *new admits* because a false admit is a double-run. A missed cluster
*turn* is unfairness. Hanging `stream_turn` wedges an already-accepted session.

**Decision**: collaborator error/timeout → skip cluster permit, keep the local 072
grant (ADR 0021 D5). Log nothing that includes DSN/principal of others.

## R5 — Call site today

Verified production use of `model_turn`:

- `src/loopplane/loop/loop.py` around the model stream (one site)

No webapi router change is required for the happy path. 085 run-start wrapping stays
as-is (ADR 0021 D8).

## R6 — Storage honesty

Same bar as ADR 0020 D2: in-memory default (tests); optional Postgres via
`loopplane[postgres]`; no File/SQLite permit backend; no new extra.

Permits are not 085 grants. Separate tables if Postgres is used.

## R7 — What "fair" means in tests

SC-001: two ready principals, two simulated workers, a burst of starts → both obtain
at least one start when `max_consecutive_starts` is 1 and `max_active_model_calls`
is 1 at cluster scope. A must not take every start while B is ready.

Single ready principal is not blocked waiting for an absent peer (US1.2).
