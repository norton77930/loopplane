"""US5: embed the host as a local sidecar — start/stop lifecycle (FR-040/041,
SC-006). In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.studio import ErrorView, InProcessSidecar, RunResultView, SidecarHost
from tests.studio_helpers import build_test_host, multi_text_model


@pytest.mark.anyio
async def test_in_process_sidecar_lifecycle(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("hello"), tools=())
    sidecar = InProcessSidecar(host)
    assert isinstance(sidecar, SidecarHost)

    # A command before start → an explicit not-available view.
    before = await sidecar.run("x")
    assert isinstance(before, ErrorView)
    assert before.kind == "not-available"

    await sidecar.start()
    result = await sidecar.run("go")
    assert isinstance(result, RunResultView)
    assert result.termination_reason == "natural-completion"
    assert sidecar.studio is not None

    await sidecar.stop()
    await sidecar.stop()  # idempotent — no orphaned run
    assert sidecar.studio is None

    # A command after stop → an explicit not-available view.
    after = await sidecar.run("again")
    assert isinstance(after, ErrorView)
    assert after.kind == "not-available"
