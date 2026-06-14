"""Runnable example: drive the LoopPlane CLI core programmatically (unit 017).

Public-safe and credential-free. The CLI's `run_once` runs one prompt through the
host and renders it from the normalized event stream to any text stream — here a
captured buffer, with a scripted model. From a shell you would instead run
`loopplane run "<prompt>"`.

Run::

    python examples/cli_quickstart.py
"""

from __future__ import annotations

import io

import anyio

from loopplane.cli import run_once
from loopplane.host import LoopPlaneHost, RuntimeConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement


async def main() -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[TextIncrement(text="Hello from the LoopPlane CLI core!")]
            )
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(RuntimeConfig(model=model))

    out = io.StringIO()
    outcome = await run_once(host, "say hello", out)

    print(out.getvalue(), end="")
    print(f"(termination: {outcome.termination_reason}, turns: {outcome.turns_taken})")


if __name__ == "__main__":
    anyio.run(main)
