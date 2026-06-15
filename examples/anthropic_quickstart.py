"""Anthropic (Claude) quickstart: drive one real model turn through the host (020).

Unlike the other examples this calls a **real** model, so it needs a key. Set
``ANTHROPIC_API_KEY`` and ``LOOPPLANE_ANTHROPIC_MODEL`` to run it; without them it
prints a message and exits. The credential is read from the environment, not committed.
"""

from __future__ import annotations

import os

import anyio

from loopplane.events import RuntimeEvent
from loopplane.host import LoopPlaneHost, RuntimeConfig


async def _run(model_name: str) -> int:
    from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel

    model = AnthropicModel(AnthropicConfig(model=model_name))
    host = LoopPlaneHost(RuntimeConfig(model=model))

    async def on_event(event: RuntimeEvent) -> None:
        print(f"{event.sequence:>3}  {event.type}")

    outcome = await host.run("Reply with a short greeting.", on_event)
    print(f"ended: {outcome.termination_reason}")
    return 0


def main() -> int:
    model_name = os.environ.get("LOOPPLANE_ANTHROPIC_MODEL")
    if not (os.environ.get("ANTHROPIC_API_KEY") and model_name):
        print("set ANTHROPIC_API_KEY and LOOPPLANE_ANTHROPIC_MODEL to run this example")
        return 0
    return anyio.run(_run, model_name)


if __name__ == "__main__":
    raise SystemExit(main())
