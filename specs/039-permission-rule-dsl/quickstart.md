# Quickstart: Validating the permission rule DSL

This guide proves the declarative permission rule DSL works end-to-end through the Tool
Gateway decide stage: an arg-regex deny rule denies a matching call (and lets a non-matching
one fall to the default), a path-glob deny rule denies a matching path, an allow rule
allows, an `ask` rule routes through the existing approval round-trip, deny-wins on conflict,
and an invalid regex is a clear config error. All scenarios are offline and deterministic (a
scripted interaction broker for the `ask` path; no real reviewer, model, or network).

## Prerequisites

- A dev install of the repo (`uv sync` / `pip install -e ".[dev]"`), Python 3.12+.
- No API key and no network are needed.

## Automated validation (primary)

Run the new offline tests plus the governance/host-config suites to confirm no regression:

```powershell
uv run pytest tests/unit/test_rule_dsl_policy.py tests/contract/test_host_config.py -q
```

Then the full quality gates:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

**Expected**: all green; every existing tool / descriptor / policy / approval test
unchanged.

## What the tests assert (mapping to acceptance scenarios)

- **Arg-regex deny** (US1): a rule `{tool: "run_command", match: {command: "^rm -rf"},
  decision: "deny"}` with `default="allow"` denies `run_command(command="rm -rf /")` (US1-1)
  and **allows** `run_command(command="ls -la")` via the default (US1-2); a *different* tool
  is unaffected (US1-3).
- **Path-glob deny + allow rule** (US2): a rule `{tool: "write_file", match: {path:
  "**/secrets/**"}, decision: "deny"}` denies `write_file(path="app/secrets/key.pem")`
  (US2-1) and **allows** `write_file(path="app/notes.md")` via the default (US2-2); an
  `{tool: "read_file", decision: "allow"}` rule allows `read_file` (US2-3).
- **`ask` round-trip + precedence** (US3): driven against a broker scripted to **approve**,
  an `ask` rule yields `PolicyAllow` (US3-1); scripted to **reject**, or with **no reviewer
  attached**, it yields `PolicyDeny` (US3-2); a matching `allow` + `deny` → deny (deny-wins,
  US3-3); a call matching no rule → the `default` (US3-4).
- **Invalid regex is a config error** (US4): constructing `rule_dsl_policy` over a rule with
  `match: {command: "["}` raises a clear error at construction (US4-1); a raising composed
  chain still denies — fail-closed (US4-2).
- **Empty is a no-op** (US5): an empty `rule_dsl_policy` with `default="allow"` composed with
  another decider equals that decider alone for any call (US5-1); a `RuntimeConfig` without
  `permission_rules` builds the same decider as today (US5-2).
- **Assembly wiring**: a `RuntimeConfig(permission_rules=PermissionRuleSet(...))` with a
  registered `run_command` builds a decider that **denies** the matching call;
  `from_mapping({... "permission_rules": {...}})` round-trips; the config still declares no
  secret field.

## Manual smoke (optional)

Build the policy over a rule set and decide a couple of calls:

```python
import anyio
from loopplane.context import RunContext
from loopplane.governance import PermissionRuleSet, PermissionRuleSpec, rule_dsl_policy
from loopplane.model import ToolCallRequest, ToolDescriptor

rules = PermissionRuleSet(
    rules=(
        PermissionRuleSpec(tool="run_command", match={"command": "^rm -rf"}, decision="deny"),
        PermissionRuleSpec(tool="write_file", match={"path": "**/secrets/**"}, decision="deny"),
        PermissionRuleSpec(tool="read_file", decision="allow"),
    ),
    default="allow",
)
policy = rule_dsl_policy(rules)

def desc(name: str) -> ToolDescriptor:
    return ToolDescriptor(name=name, description="", input_schema={})

async def main() -> None:
    ctx = RunContext(session_id="s", working_scope=__import__("pathlib").Path("."))
    rm = await policy(
        ToolCallRequest(call_id="c", tool_name="run_command", input={"command": "rm -rf /"}),
        desc("run_command"), ctx, None)
    ls = await policy(
        ToolCallRequest(call_id="c", tool_name="run_command", input={"command": "ls"}),
        desc("run_command"), ctx, None)
    secret = await policy(
        ToolCallRequest(call_id="c", tool_name="write_file", input={"path": "a/secrets/k"}),
        desc("write_file"), ctx, None)
    print(type(rm).__name__, type(ls).__name__, type(secret).__name__)
    # PolicyDeny PolicyAllow PolicyDeny

anyio.run(main)
```

To wire it through the host, set `permission_rules`:

```python
from loopplane.governance import PermissionRuleSet, PermissionRuleSpec
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.tools import InternalToolAdapter

host = LoopPlaneHost(
    RuntimeConfig(
        model=model,
        tool_adapters=(InternalToolAdapter(),),
        permission_rules=PermissionRuleSet(
            rules=(
                PermissionRuleSpec(tool="run_command", match={"command": "^rm -rf"}, decision="deny"),
                PermissionRuleSpec(tool="mcp:*", decision="ask"),
            ),
            default="allow",
        ),
    )
)
```

With rules present, every tool call is decided against them at the Gateway decide stage
(deny-wins, fail-closed, composed with the network/approval/plan-mode gates). An `ask` rule
escalates to the attached human through the existing approval round-trip. Leaving
`permission_rules` at its default (`None`) leaves runs exactly as before.

## Rollback

The feature is additive. To roll back, remove `src/loopplane/governance/rule_dsl.py` and its
export, the `RuntimeConfig.permission_rules` field + its `from_mapping` coercion, the
`_build_decider` rule-DSL composition, the api-reference bullets, and the new test module;
the baseline tool set, the gateway, the loop, the approval boundary, and every policy are
untouched (Constitution X).
