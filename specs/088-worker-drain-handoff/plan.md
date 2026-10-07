# Implementation Plan: Worker Drain Handoff

**Branch**: `088-worker-drain-handoff` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/088-worker-drain-handoff/spec.md`

## Summary

Add an opt-in per-worker drain flag on the existing admission coordinator.
While the flag is set, a new `hold` refuses with the existing capacity
rejection before it takes a grant. A hold that already started keeps running
and still releases. Peer workers that share the store are unchanged, so they
can take the principal after release. No store schema, HTTP route, event, or
dependency is added.

## Technical Context

**Language/Version**: Python 3.11 (repository baseline)
**Primary Dependencies**: existing `anyio` admission coordinator; no new package
**Storage**: none. The flag lives on the coordinator instance, not in the grant store
**Testing**: pytest, existing admission unit tests plus one focused module section
**Target Platform**: the web/API worker process that already hosts `AdmissionCoordinator`
**Project Type**: library, opt-in serving control
**Performance Goals**: one boolean check on the admit path; no extra round trip
**Constraints**: default off; in-flight body is not cancelled; public phrase stays
`capacity exceeded`; representations stay redacted
**Scale/Scope**: one flag and two methods on the coordinator. Not a cluster drain record.

## Constitution Check

Pre-research and post-design: PASS.

- I: spec, plan, tasks, and this session's maintainer request precede implementation.
- II/IX: behavior is derived from units 085–087 and gap C4. No private reference material.
- III/IV: admission keeps ownership of the serving lease. The flag is not a second store.
- V/VI: no Gateway, Event Bus, checkpoint, termination vocabulary, or outward phrase change.
- VII: coordinator `repr` stays `AdmissionCoordinator()`.
- VIII: no framework substitution or new dependency.
- X: one focused RED test before the coordinator change.

§E assessment: no existing default, dependency, extra, event or checkpoint schema,
Gateway SPI, HTTP route, or release is changed. Reusing the capacity rejection
does not add a public string. No ADR is required: the accepted 085 boundary
(serving-layer lease above the pool) is unchanged, and 086/087 artifacts are not rewritten.

## Project Structure

### Documentation (this feature)

`spec.md`, `checklists/requirements.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/worker-drain.md`, `quickstart.md`, `tasks.md`, `implementation-evidence.md`.

### Source Code (repository root)

- `src/loopplane/webapi/admission.py`: `begin_drain`, `end_drain`, and the pre-take refusal.
- `tests/unit/test_webapi_admission.py`: the handoff and unchanged-path checks.
- `docs/api-reference.md`: one sentence on the two methods.
- `docs/loopplane-agent-board.md` and `docs/gap-analysis.md`: record the slice and the deferred mid-turn tail.

**Structure Decision**: keep the flag on `AdmissionCoordinator`. The shared store
must not learn about drain, or one worker's rollout would refuse peers.
