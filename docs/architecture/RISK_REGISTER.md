# Architecture Risk Register

> Each entry: risk / affected area / evidence path / severity / likelihood / why a future AI may make this mistake / mitigation / human approval gate / verification method. Severity·likelihood ∈ {High, Med, Low}. Source: the 2026-07-06 read-only audit (`ARCHITECTURE_AUDIT.md`).

## R1 — `context.py` boundary converted to top-level imports

- **Affected**: `src/loopplane/context.py` → the whole controller/tools/assembly chain
- **Evidence**: `context.py` (TYPE_CHECKING-only import; neutral Protocols)
- **Severity/Likelihood**: High / High
- **Why AI errs**: the linter/IDE instinct to "organize imports" or "deduplicate" moves the TYPE_CHECKING block to top level; nothing looks broken statically
- **Mitigation**: boundaries doc §1 cautions; longer term, an import linter (see R10)
- **Gate**: any change to `context.py`
- **Verify**: `uv run pytest tests/contract -q` + grep that `from loopplane.tools` exists only at the two sanctioned sites

## R2 — Unversioned event-schema change

- **Affected**: `src/loopplane/events/envelope.py` (`SCHEMA_VERSION = 1`); 23 downstream files + SSE/replay/checkpoint serde
- **Severity/Likelihood**: High / Med
- **Why AI errs**: "just add one field" looks additive but is an outward contract change
- **Mitigation**: G2; schema changes need a version bump + compatibility note
- **Gate**: always · **Verify**: events/webapi/checkpoint contract tests

## R3 — Gateway bypass

- **Affected**: `gateway/gateway.py`, `gateway/spi.py`, all adapters
- **Severity/Likelihood**: High / Med
- **Why AI errs**: caching or delegating `.invoke()` inside an adapter for performance/convenience; delegation wrappers dispatching outside the Gateway have previously tripped the Constitution-V audit (unit 043)
- **Mitigation**: G1; the Gateway is the only caller of `.invoke()`
- **Gate**: SPI/stage changes · **Verify**: grep where `.invoke(` appears + gateway contract tests

## R4 — `host/assembly.py` lazy imports get "tidied"

- **Affected**: the optional-extra boundary; the import cycle (engineering → host → assembly)
- **Severity/Likelihood**: High / Med
- **Why AI errs**: lazy imports look like a code smell; the refactoring instinct is to hoist them to the file top
- **Mitigation**: boundaries doc §2 cautions; in-file comments
- **Gate**: assembly wiring changes · **Verify**: `python -c "import loopplane.host"` in an extras-free environment

## R5 — Default-off / byte-identity defaults changed

- **Affected**: every `RuntimeConfig` knob (budget/compaction/subagents/permission_mode/…)
- **Severity/Likelihood**: High / Med
- **Why AI errs**: "this feature is great, let's turn it on by default"
- **Mitigation**: G5 · **Gate**: always · **Verify**: byte-identity tests under default config (most units ship one)

## R6 — Checkpoint record serde breaks resume

- **Affected**: `checkpoint/records.py`, `checkpoint/rebuild.py`
- **Severity/Likelihood**: High / Low–Med
- **Why AI errs**: changing a record field without considering that old session files must still rebuild
- **Mitigation**: G3; `RECORD_SCHEMA_VERSION` control · **Gate**: always · **Verify**: checkpoint contract + parity tests

## R7 — `webapi/auth_jwt.py` security logic subtly weakened

- **Affected**: JWKS refresh throttle / negative-kid cache / single-flight (units 056/067, default-ON)
- **Severity/Likelihood**: High / Low
- **Why AI errs**: a refactor can break throttle timing or lock scope while tests stay green
- **Mitigation**: the unit-067 tests (`tests/unit/test_jwks_hardening.py`); auth-path changes need a security-focused review
- **Gate**: auth-path changes · **Verify**: `uv run pytest tests/unit/test_jwks_hardening.py tests/unit/test_oauth_verifier.py -q`

## R8 — Old tasks checkboxes misread as unfinished work

- **Affected**: tasks.md of `specs/001, 015–039, 043`
- **Severity/Likelihood**: Med / High
- **Why AI errs**: a naive scan sees `[ ]` and schedules the work
- **Mitigation**: `SPEC_KIT_ALIGNMENT_RULES.md` §9; `docs/spec-task-audit-exceptions.md`
- **Gate**: changes to the reconciliation exception list · **Verify**: `uv run pytest tests/contract/test_spec_task_audit.py -q`

## R9 — README / CHANGELOG staleness misleads

- **Affected**: README (unit-013 era), CHANGELOG/`__version__` (0.4.0 / unit 063)
- **Severity/Likelihood**: Med / High
- **Why AI errs**: concluding from the README that a feature "does not exist" and re-implementing it, or inferring the capability envelope from 0.4.0
- **Mitigation**: the source-of-truth ladder; pay down the debt per `RELEASE_SYNC_RULES.md`
- **Gate**: release actions · **Verify**: cross-check against the board

## R10 — Boundaries lack a static gate

- **Affected**: all import-direction rules (new packages/new edges are not protected by existing contract tests)
- **Severity/Likelihood**: Med / Med
- **Why AI errs**: when adding a package, nothing says a boundary test must come with it
- **Mitigation**: short term — every new package ships a `test_<pkg>_boundary`; long term — evaluate an import linter in CI (needs maintainer approval as a new dev dependency)
- **Gate**: new packages, new dependencies · **Verify**: the contract suite

## R11 — `webapi/app.py` aggregation hotspot keeps growing

- **Affected**: `webapi/app.py` (units 064/071/074/075 kept adding routes)
- **Severity/Likelihood**: Med / Med
- **Why AI errs**: "just add one more route" is the path of least resistance; over time auth/pool/principal boundaries blur
- **Mitigation**: pass boundaries doc §3 cautions before adding routes; split via a dedicated spec when warranted (a product decision)
- **Gate**: outward contract changes · **Verify**: the web contract suites

## R12 — Bulk `git add` sweeps in unrelated changes

- **Affected**: git history; public safety
- **Severity/Likelihood**: Med / Med
- **Why AI errs**: habitual `git add <dir>` + commit chains in autopilot can sweep unrelated WIP or unreviewed files into a commit
- **Mitigation**: reset → add files individually → review the staged list as a separate step → commit (`AI_HANDOFF_OPERATING_TEMPLATE.md` §F)
- **Gate**: the staged-list review before any commit · **Verify**: `git status --short`, item by item

## R13 — Stale examples teach old style

- **Affected**: `examples/` (covers only the ~001–024 era)
- **Severity/Likelihood**: Low / Med
- **Why AI errs**: agents treat examples as API templates and write code that ignores newer guards (budget, permission modes)
- **Mitigation**: extend examples to newer capabilities (needs its own unit); the template's §A excludes examples from required reading
- **Gate**: none · **Verify**: `tests/integration/test_examples_smoke.py`
