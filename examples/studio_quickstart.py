"""Quickstart: drive the LoopPlane desktop/studio host in-process (feature 012).

Public-safe and offline: build a host over a scripted fake model, open a
``StudioHost`` console, drive a run, and list/inspect sessions — all in-process,
no GUI, no network, no process spawn. The views are metadata-only (no
conversation content is printed).

Run: ``python examples/studio_quickstart.py``
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import anyio

from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement
from loopplane.studio import RunResultView, StudioHost


def build_demo_host(scope: Path) -> LoopPlaneHost:
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="hello from the loop")])],
        context_capacity=100_000,
    )
    return LoopPlaneHost(RuntimeConfig(model=model), working_scope=scope)


async def _main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        host = build_demo_host(Path(tmp))
        async with StudioHost(host) as studio:
            result = await studio.run("please run")
            if isinstance(result, RunResultView):
                print(
                    "run ->",
                    result.termination_reason,
                    "| turns:",
                    result.turns_taken,
                )
                # Metadata-only: roles + counts, never the conversation content.
                print("history (metadata-only):", result.history)
                print("history view:", studio.history_view(result.session_id))

            sessions = studio.list_sessions()
            print("sessions ->", len(sessions))


if __name__ == "__main__":
    anyio.run(_main)
