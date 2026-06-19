# Requirements Quality Checklist: Dynamic Subagents (043)

A pre-implementation gate that the spec is complete, unambiguous, and consistent. Each item is
verifiable against `spec.md`.

## Scope & boundary

- [x] CHK001 Scope is a single, bounded, model-driven **one-shot** spawn (not a swarm). [Spec §Scope, NFR-004]
- [x] CHK002 Out-of-scope items are explicitly named (messaging, swarm/peer, persistent/named/background
      subagents, live-event streaming, cross-host). [Spec §Reserved extension points]
- [x] CHK003 The child is driven through the **existing** Phase-3 `run_loop` — no agent-loop rewrite. [FR-002, NFR-001]
- [x] CHK004 The tool is reachable only through the Tool Gateway (Constitution V). [FR-004, NFR-002]

## Recursion safety (the riskiest requirement)

- [x] CHK010 An additive `subagent_depth` (default 0) is on the run context; a child is parent+1. [FR-010]
- [x] CHK011 A configurable `max_subagent_depth` (default 0 = off; set to a small value like 1 to enable) bounds the nesting. [FR-011]
- [x] CHK012 At/over the cap, the spawn is **denied** with a normalized error and **no** child run starts. [FR-011, SC-002]
- [x] CHK013 `max_subagent_depth = 0` means the tool is not registered at all (opt-out). [FR-012]
- [x] CHK014 A test proves no unbounded nesting (zero child runs at the cap). [SC-002]

## Failure containment

- [x] CHK020 A child that raises / fails validation / terminates non-naturally / pauses / answers empty
      is contained to a normalized result; the parent never crashes. [FR-020, NFR-005]
- [x] CHK021 No raw exception, stack trace, secret, or private path is returned. [FR-020, NFR-006]
- [x] CHK022 A child over-run is bounded (gateway per-call timeout + one-iteration child loop). [Spec §Edge Cases]

## Events & artifacts (Constitution VI)

- [x] CHK030 Child events are captured metadata-only (reusing 013 aggregation), never re-emitted on the
      parent's live bus. [FR-030, NFR-003, SC-005]

## Result contract

- [x] CHK040 Success returns the child's **final assistant text** as a `TextBlock`; not steps/IO/events. [FR-003]
- [x] CHK041 Restricted toolset: `allowed_tools` intersects the parent tools; omitted → inherit parent. [FR-040]

## Quality & verification

- [x] CHK050 All behavior is deterministic, offline, in-process (ScriptedModel parent + child). [NFR-006, NFR-007]
- [x] CHK051 Additive with a clear rollback (`max_subagent_depth = 0` / not opting in disables it). [NFR-007, SC-004]
- [x] CHK052 The agent loop, orchestration core, gateway pipeline, event schema, and content model are
      unchanged (no `SCHEMA_VERSION` bump). [SC-004, NFR-001]
- [x] CHK053 Each requirement has at least one acceptance scenario and a measurable success criterion.
