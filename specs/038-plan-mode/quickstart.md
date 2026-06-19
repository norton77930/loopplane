# Quickstart: Validating Plan Mode

This guide proves plan mode works end-to-end through the Tool Gateway decide stage:
while planning, non-read-only tools are denied and read-only + the allowlist are
allowed; `exit_plan_mode` clears plan mode on approval (and keeps it on reject / no
human). All scenarios are offline and deterministic (a scripted interaction broker; no
real reviewer, model, or network).

## Prerequisites

- A dev install of the repo (`uv sync` / `pip install -e ".[dev]"`), Python 3.12+.
- No API key and no network are needed.

## Automated validation (primary)

Run the new offline tests plus the governance/host-config suites to confirm no
regression:

```powershell
uv run pytest tests/unit/test_plan_mode_policy.py tests/unit/test_plan_mode_tool.py tests/contract/test_host_config.py -q
```

Then the full quality gates:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

**Expected**: all green; every existing tool / descriptor / policy test unchanged.

## What the tests assert (mapping to acceptance scenarios)

- **Plan-mode policy** (US1): with an active `PlanModeState`, a non-read-only descriptor
  (`write_file` / `run_command`) is **denied** (US1-1); read-only descriptors
  (`read_file` / `grep` / `glob_files` / `search_files`) are **allowed** (US1-2); the
  allowlist (`ask_user` / `exit_plan_mode`) is **allowed** even though not read-only
  (US1-3); a raising policy in the composed chain still denies — fail-closed (US1-4).
- **`exit_plan_mode` approve** (US2): driven against a broker scripted to answer
  `approve`, the holder becomes inactive and the tool returns a success `TextBlock`
  (US2-1); a subsequent `write_file` decision then **allows** (US2-2).
- **`exit_plan_mode` reject / no human** (US3): driven against a broker scripted to
  reject, plan mode stays active and the tool returns a clear "not approved" outcome
  (US3-1); with **no reviewer attached**, plan mode stays active and the tool returns a
  normalized `ErrorOutput` (US3-2); a subsequent `write_file` decision still **denies**
  (US3-3).
- **Off is a no-op** (US4): with no `PlanModeState` (or one with `active=False`), the
  policy allows every tool including non-read-only ones (US4-1); a `RuntimeConfig`
  without `plan_mode` builds the same decider as today (US4-2).
- **Assembly wiring**: a `RuntimeConfig(plan_mode=True)` with a registered `write_file`
  builds a decider that **denies** `write_file` for a context whose `plan_mode` is
  active; `from_mapping({... "plan_mode": True})` round-trips.

## Manual smoke (optional)

Build the policy over a holder and decide a couple of descriptors:

```python
import anyio
from loopplane.context import PlanModeState, RunContext
from loopplane.governance import plan_mode_policy
from loopplane.model import ToolCallRequest, ToolDescriptor

state = PlanModeState(active=True)
policy = plan_mode_policy(state)

def desc(name: str, *, read_only: bool) -> ToolDescriptor:
    return ToolDescriptor(name=name, description="", input_schema={}, read_only=read_only)

async def main() -> None:
    ctx = RunContext(session_id="s", working_scope=__import__("pathlib").Path("."))
    write = await policy(ToolCallRequest(call_id="c", tool_name="write_file", input={}),
                         desc("write_file", read_only=False), ctx, None)
    read = await policy(ToolCallRequest(call_id="c", tool_name="read_file", input={}),
                        desc("read_file", read_only=True), ctx, None)
    print(type(write).__name__, type(read).__name__)  # PolicyDeny PolicyAllow
    state.active = False
    after = await policy(ToolCallRequest(call_id="c", tool_name="write_file", input={}),
                         desc("write_file", read_only=False), ctx, None)
    print(type(after).__name__)  # PolicyAllow (no-op when inactive)

anyio.run(main)
```

To wire it through the host, set `plan_mode=True`:

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.tools import InternalToolAdapter

host = LoopPlaneHost(
    RuntimeConfig(
        model=model,
        tool_adapters=(InternalToolAdapter(),),  # provides exit_plan_mode + the file tools
        plan_mode=True,
    )
)
```

With `plan_mode=True`, every run starts in plan mode: the agent investigates with
read-only tools and `ask_user`, proposes a plan, and calls `exit_plan_mode`; once the
attached human approves, non-read-only tools become allowed and the agent executes.
Leaving `plan_mode` at its default (`False`) leaves runs exactly as before.

## Rollback

The feature is additive. To roll back, remove `src/loopplane/governance/plan_mode.py`
and its export, the `PlanModeState` holder + the `RunContext.plan_mode` field, the
`exit_plan_mode` descriptor/handler in `tools/internal.py`, the
`RuntimeConfig.plan_mode` field, the `RuntimeController` `plan_mode` kwarg + the
`drive()` line, the `_build_decider` plan-mode composition, the api-reference bullet,
and the new test modules; the baseline tool set, the gateway, the loop, and every policy
are untouched (Constitution X).
