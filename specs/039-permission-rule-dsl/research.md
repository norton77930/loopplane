# Phase 0 Research: Declarative permission rule DSL

All decisions favour reuse of the existing Tool Gateway decide-stage seam, the existing
`governance` combinators, the existing `PermissionRule` / `resolve_rules` matcher +
precedence engine, the existing binary `PolicyVerdict`, and the existing human approval
round-trip. The design is additive and default-empty. No NEEDS CLARIFICATION remained from
the spec. Every claim below was verified by reading the real code (file:line cited).

## Seam verification (read before designing)

### S1 — The verdict model: there is NO "ask" verdict (the crux)

- `PolicyVerdict = PolicyAllow | PolicyDeny` (`src/loopplane/approval/decisions.py:25`).
  `PolicyAllow` is an empty frozen dataclass; `PolicyDeny(reason: str)`. The decide-stage
  `PolicyDecider` is `(ToolCallRequest, ToolDescriptor, RunContext, EventEmitter) ->
  Awaitable[PolicyVerdict]` (same file, line 27). **There is no `PolicyAsk` type.**
- "Ask" is **not a verdict** — it is **behaviour inside a decider**. The Human Approval
  boundary realizes it in `HumanApproval._escalate`
  (`src/loopplane/approval/approval.py:90`): it calls
  `context.interactions.request_approval(call_id=..., tool_name=..., input_summary=...)`,
  awaits the `ApprovalResolution`, optionally records session memory, and returns
  `PolicyAllow()` on `decision == "allow"` else `PolicyDeny(reason=...)`. With **no broker /
  no reviewer attached** it returns `PolicyDeny("no reviewer available")` (line 95) — it
  never hangs and never silently allows.
- `InteractionBroker.request_approval` (`src/loopplane/approval/interactions.py:76`) emits
  `approval_requested`, awaits the pending event, emits `approval_resolved`, and returns the
  `ApprovalResolution(decision: "allow"|"deny", scope, reason, source)`. A reviewer
  disconnect (`on_disconnect`, line 58) resolves every pending approval as **deny** — so an
  `ask` that loses its reviewer mid-decision denies, never hangs.

**Implication (the key design choice)**: the DSL's `decision: ask` must **reuse this exact
path** — call `context.interactions.request_approval(...)` and map the resolution to
`PolicyAllow` / `PolicyDeny` — rather than inventing a new verdict or approval mechanism
(FR-003). This makes `rule_dsl_policy` an **async, context-reading** decider (it needs the
per-run `RunContext` for `ask`), like `plan_mode_policy` — **not** a context-free
`as_decider` wrapper (which is for `permission_policy` / `network_policy`, whose decisions
need only the call + descriptor). The `allow` / `deny` decisions still need only the call +
descriptor; only `ask` reads the context, and `safe_failure` already maps a missing-broker
raise to deny if ever reached.

### S2 — The existing rule precedence + matcher to reuse

- `PermissionRule(matcher: str, effect: "allow"|"deny", scope)` +
  `resolve_rules(rules, tool_name)` (`src/loopplane/approval/rules.py`). `resolve_rules`
  matches by `fnmatch.fnmatchcase(tool_name, rule.matcher)` (so `mcp:*` matches
  `mcp:server:tool`), takes the **most-local scope** among matched rules, and within that
  scope **deny overrides allow**; no match → `None`.
- `permission_policy` (`src/loopplane/governance/permission.py`) already reuses
  `resolve_rules` deny-wins and falls back to a configurable `default` (default `deny`).

**Implication**: the DSL reuses (a) the **`fnmatch` matcher syntax** for its `tool`
dimension (so `mcp:*` etc. work identically to the existing matcher), and (b) the
**deny-wins** precedence. The DSL adds **two new matcher facets the existing engine lacks**
— an **arg-regex** (`call.input[field]` vs a regex) and a **path-glob** (`call.input[field]`
vs a glob) — and a third decision (`ask`). For the combined precedence the DSL generalizes
deny-wins to **deny > ask > allow** (ask is more conservative than allow). When all matching
rules are name-only allow/deny, this reduces to `resolve_rules`' deny-wins. The DSL does
**not** expose scope as a host-facing field (Out of Scope); it reuses the *concept* (deny
wins) flatly.

### S3 — What the decide-stage decider receives + where it is composed

- The decider is called `await self._decide(call, tool.descriptor, context, emitter)` in the
  Tool Gateway (`gateway.py`), so it receives the per-run `RunContext` (carrying
  `interactions`) and the `ToolDescriptor`. `ToolCallRequest` carries `call_id`, `tool_name`,
  and `input: dict[str, object]` (`src/loopplane/model/boundary.py:67`).
- `_build_decider` (`src/loopplane/host/assembly.py:159`) builds the decider once at assembly
  and composes the existing deciders as
  `safe_failure(all_of(<approval?>, network_policy, <plan_mode?>))` — **deny-wins**
  (`all_of`, `combine.py:22`, short-circuits on the first `PolicyDeny`) + **fail-closed**
  (`safe_failure`, `combine.py:44`, maps any raise to deny). `network_policy` /
  `plan_mode_policy` are the precedents: an additive decider appended to the `deciders` list,
  with **no new gateway stage**.

**Implication**: append `rule_dsl_policy(config.permission_rules)` to the same `deciders`
list when `permission_rules` is present, and extend the gate that decides whether *any*
decider is built (`approval_needed or network_gate_needed or plan_mode_needed`) with
`rules_needed = config.permission_rules is not None and bool(rules)`. The `None` fast-path is
preserved for a run with no rules (and no other gate). Because `all_of` short-circuits on a
`PolicyDeny`, a DSL `deny` (or an `ask` the human rejects) wins over a later allow exactly as
required; a DSL `ask` that the human *approves* returns `PolicyAllow`, then the chain
continues to the other deciders (so network/approval/plan-mode can still deny) — the correct
deny-wins composition.

### S4 — Config wiring (how flags/policies are carried)

- `RuntimeConfig` (`src/loopplane/host/config.py:84`) is a frozen dataclass; optional
  subsystems default to off (`approval: ApprovalPolicy | None = None`, `allow_network: bool =
  False`, `plan_mode: bool = False`). `from_mapping` (line 110) coerces each — object
  collaborators pass through, scalars/structured selections are coerced by small `_coerce_*`
  helpers. `ApprovalPolicy` is a frozen dataclass with `allow`/`deny`/`ask` frozensets + a
  `default`. A contract test (`tests/contract/test_host_config.py:105`) asserts the config
  declares **no secret field**.

**Implication**: add `permission_rules: PermissionRuleSet | None = None` (default `None` =
no rules) and a `_coerce_permission_rules` helper that accepts a `PermissionRuleSet`
unchanged or builds one from a mapping `{"rules": [ {tool, match?, decision}, ... ],
"default": "allow"|"deny"|"ask"}`. The field carries only tool names + patterns + decisions
(no secret), so the existing no-secret test still passes.

### S5 — Constitution constraints

- **V**: the Tool Gateway is the single enforcement chokepoint; the rule DSL is a
  decide-stage **policy**, never a bypass; it never resolves/executes a tool.
- **VI**: no event-schema change — `ask` reuses the existing `approval-requested` /
  `approval-resolved` events; no new event type, no `SCHEMA_VERSION` bump.
- **IV**: don't blur a runtime boundary; the DSL reuses the Gateway decide seam and the
  existing approval round-trip — no new cross-component channel → no ADR.
- **VII**: rules are public-safe (tool names + patterns + decisions only).
- **X**: TDD + rollback — covered by Phase 2 tasks and the plan's rollback note.

## Decision 1 — A new `governance/rule_dsl.py`, composed via the existing combinators

- **Decision**: Add `governance/rule_dsl.py` with the rule shapes (`PermissionRuleSpec`,
  `PermissionRuleSet`) and `rule_dsl_policy(rules: PermissionRuleSet) -> PolicyDecider`. The
  returned async decider selects matching rules, combines deny>ask>allow, falls back to
  `default`, and returns the existing verdict (reusing `request_approval` for `ask`). Compose
  it in `_build_decider` as one more decider in
  `safe_failure(all_of(<approval?>, network_policy, <plan_mode?>, rule_dsl_policy(...)))`.
- **Why a new module (not extending `governance/permission.py`)?** `permission_policy`
  reuses `resolve_rules`, which is **name-only** (matcher → effect). The DSL adds two new
  matcher facets (arg-regex, path-glob) and a third decision (`ask`) that the name-only
  engine cannot express, and it must be **async** (for the `ask` round-trip). A cohesive new
  module sibling to `network.py` / `plan_mode.py` is the house pattern; `permission_policy`
  stays unchanged for callers that want the simple name-only form.
- **Rationale**: Mirrors `network_policy` / `plan_mode_policy` (an additive decider, no new
  stage, V). `all_of` already gives deny-wins and `safe_failure` already gives fail-closed —
  exactly the required composition, reused verbatim.
- **Alternatives considered**: A new Gateway stage (rejected: violates V / "reuse the
  existing seam"); extending `PermissionRule`/`resolve_rules` with regex + ask (rejected: it
  would change the runtime rule type the Human Approval boundary depends on, and make a
  synchronous engine async — a wider blast radius than an additive sibling module).

## Decision 2 — The rule shape + matcher + precedence

- **Decision**: `PermissionRuleSpec(tool: str, match: Mapping[str, str] | None = None,
  decision: "allow"|"deny"|"ask")` and `PermissionRuleSet(rules: tuple[PermissionRuleSpec,
  ...] = (), default: "allow"|"deny"|"ask" = "allow")`, both frozen pydantic models (matching
  `PermissionRule`'s `BaseModel` + `ConfigDict(frozen=True)` style). A rule **matches** a
  call iff: (a) `fnmatchcase(call.tool_name, rule.tool)` (the existing matcher syntax), AND
  (b) for **every** `(field, pattern)` in `match`, the field is present in `call.input` and
  its **string form** satisfies the pattern. A `match` value is interpreted as a **path-glob**
  for path-shaped fields and a **regex** otherwise — see Decision 3 for the disambiguation.
- **Precedence**: among the rules that match, **deny > ask > allow** (deny short-circuits the
  whole composed chain via `all_of`; ask is more conservative than allow). No rule matches →
  the set's `default`. This generalizes `resolve_rules`' deny-wins (when every matching rule
  is name-only allow/deny it reduces to exactly that) and stays SAFE (the most-restrictive
  matching decision wins).
- **Rationale**: Reuses the `fnmatch` matcher syntax verbatim (so `mcp:*` works), keeps the
  rule flat + public-safe, and makes precedence a single documented total order. A `match`
  that names an **absent** field does not match (so a `deny` gates a *specific present
  invocation*, never a call lacking the field — it then falls through to other rules /
  default), matching the spec's edge case.
- **Alternatives considered**: rule **order wins** (rejected: order-dependence is surprising
  and unsafe — a stray late `allow` could shadow an earlier `deny`; deny-wins is the house
  posture); a list of regexes per field (rejected: one pattern per field is the minimal,
  clear shape; multiple rules cover "any of").

## Decision 3 — Disambiguating path-glob from regex in `match`

- **Decision**: A `match` entry is treated as a **path-glob** when its field name is
  **path-shaped** (`path` or any field name ending in `_path`, plus `file`) and as a
  **regex** otherwise. Both are **compiled/validated eagerly at construction**: the regex via
  `re.compile` (a malformed pattern raises `re.error` → a clear config error), and the glob
  via `fnmatch.translate` + `re.compile` (so a path-glob is matched as a translated regex,
  supporting `**`/`*`/`?`). A path-glob test normalizes the field's string value to forward
  slashes before matching (so a Windows-style `\\` path still matches a `/`-glob).
- **Why field-name-based disambiguation?** The DSL is call-shaped and the call input is an
  untyped `dict[str, object]`; the field *name* is the only reliable signal of "this is a
  path". `path` is the input field every file tool uses (`write_file` / `read_file` /
  `edit_file`, verified in `tools/internal.py`), so keying the glob on `path`-shaped names is
  predictable and covers the file tools. A non-path field (e.g. `command`) uses a regex,
  which is what US1 (`^rm -rf`) needs.
- **Rationale**: One declarative `match` map serving both facets keeps the rule shape minimal
  while supporting the two matchers the spec requires; eager compilation is what makes an
  invalid pattern a construction-time error (FR-005, US4) rather than a silent decide-time
  allow.
- **Alternatives considered**: a separate `path_match` vs `arg_match` map (rejected: two maps
  for one concept — the field name already disambiguates); always-regex (rejected: a
  glob is the natural, safe way to express a path subtree and avoids users hand-writing
  path regexes); a per-entry `{type: glob|regex}` tag (rejected: more ceremony than the
  field-name convention needs this unit).

## Decision 4 — `RuntimeConfig.permission_rules` (host opt-in), default-empty

- **Decision**: Add `RuntimeConfig.permission_rules: PermissionRuleSet | None = None`
  (coerced in `from_mapping` from a `PermissionRuleSet` or a mapping `{"rules": [...],
  "default": "..."}`). In `_build_decider`, when `permission_rules` is present **and has at
  least one rule**, append `rule_dsl_policy(config.permission_rules)` to the composed
  `deciders` and ensure a decider is built; otherwise the existing gate decides (so a config
  with no rules keeps today's posture). When absent, no DSL policy is installed — an existing
  run is byte-identical.
- **Why gate installation on "has rules"?** An empty set with `default="allow"` is a pure
  no-op; not installing it preserves the allow-all `None` fast-path for a run that never uses
  the DSL (consistent with 034/038 only building a decider when a gate is actually needed).
  Even when installed, the policy with `default="allow"` and matching no rule is a no-op — so
  the gate is an optimization + a clean default, not a correctness requirement.
- **Rationale**: Mirrors `allow_network` / `plan_mode` exactly — an additive, public-safe,
  default-off config field coerced in `from_mapping`, threaded through `_build_decider`. The
  field carries no secret (VII), so the existing no-secret contract test still passes.
- **Alternatives considered**: a bare `tuple[PermissionRuleSpec, ...]` field with the default
  carried separately (rejected: bundling the rules + their default in one `PermissionRuleSet`
  is cleaner and mirrors `ApprovalPolicy` bundling its sets + default); reading a YAML file
  (rejected: no config-file format is in scope this phase — Out of Scope).

## Decision 5 — Test layout

- **Decision**: `tests/unit/test_rule_dsl_policy.py` for the policy (using
  `tests/governance_helpers.py` `call` / `descriptor` / `decide` / `decide_with_context`, and
  the scripted `InteractionBroker` round-trip from `tests/contract/test_approval.py` for the
  `ask` path — a background task answers the emitted `approval-requested`). Additive assembly
  tests in `tests/contract/test_host_config.py` for the `permission_rules` wiring (decider
  denies the matching call; `from_mapping` round-trip; no-secret).
- **Rationale**: Consistent with the repo's governance + host-config test patterns; fully
  offline and deterministic (a scripted broker, no real reviewer, no model, no network). The
  `allow` / `deny` / default / matcher / invalid-regex tests need no broker (they use
  `decide` / `decide_with_context`); only the `ask` round-trip uses the broker harness.
