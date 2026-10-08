# Quickstart: Container Command Sandbox

The default command path is unchanged. To opt in, install the extra, have a
local image, and pass the executor into the existing adapter:

```python
from loopplane.tools import DockerCommandExecutor, InternalToolAdapter

adapter = InternalToolAdapter(
    command_executor=DockerCommandExecutor(image="python:3.12-alpine")
)
```

Construction fails if `loopplane[docker]` is missing, the daemon does not
answer, or that image is not already local. The runtime does not pull it.

Focused check:

```text
uv run pytest tests/unit/test_container_executor.py tests/unit/test_sandbox_execution.py -q --tb=line
```
