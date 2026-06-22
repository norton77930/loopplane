# Quickstart: Platform Fairness

## Default Behavior

Do not configure platform fairness. Existing single-host and tenant-host-pool
behavior remains unchanged.

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig

host = LoopPlaneHost(RuntimeConfig(model=model))
```

## Enable In-Process Fairness

Configure one shared in-process fairness collaborator and reuse it across hosts
created for the same web/API process.

```python
from loopplane.fairness import PlatformFairness, PlatformFairnessPolicy
from loopplane.host import LoopPlaneHost, RuntimeConfig

fairness = PlatformFairness(
    PlatformFairnessPolicy(
        max_outstanding_per_tenant=4,
        max_active_model_calls=2,
        max_consecutive_starts=1,
    )
)

config = RuntimeConfig(model=model, platform_fairness=fairness)
host = LoopPlaneHost(config)
```

## Web/API Behavior

When the host pool and fairness are configured together:

- A tenant over its local outstanding-work quota receives HTTP 429 before the
  run starts.
- Other tenants within quota continue normally.
- Model calls from accepted work start according to the in-process fair
  scheduler.
- Runtime event schema and termination reasons are unchanged.

## Local Validation

Run the focused 072 checks first:

```powershell
uv run pytest tests/unit/test_platform_fairness.py
uv run pytest tests/unit/test_tenant_host_pool.py
uv run pytest tests/unit/test_loop_core.py
uv run pytest tests/contract/test_host_config.py
```

Then run the standard gates:

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest
```

## Rollback

Remove the fairness configuration or revert the 072 implementation commit. With
`platform_fairness=None`, the admission and model-turn gates are inert and the
pre-072 behavior is restored.
