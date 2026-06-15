"""OpenAI (GPT) quickstart: drive one real model turn through the host (020).

Unlike the other examples, this one calls a **real** model: set ``OPENAI_API_KEY`` and
``LOOPPLANE_OPENAI_MODEL`` to run it. Without them it prints a message and exits. The
credential is read from the environment by the adapter; nothing is committed.
"""

from __future__ import annotations

import os

import anyio

from loopplane.events import RuntimeEvent
from loopplane.host import LoopPlaneHost, RuntimeConfig


async def _run(model_name: str) -> int:
    from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

    model = OpenAIModel(OpenAIConfig(model=model_name))
    host = LoopPlaneHost(RuntimeConfig(model=model))

    async def on_event(event: RuntimeEvent) -> None:
        print(f"{event.sequence:>3}  {event.type}")

    outcome = await host.run("Reply with a short greeting.", on_event)
    print(f"ended: {outcome.termination_reason}")
    return 0


def main() -> int:
    model_name = os.environ.get("LOOPPLANE_OPENAI_MODEL")
    if not (os.environ.get("OPENAI_API_KEY") and model_name):
        print("set OPENAI_API_KEY and LOOPPLANE_OPENAI_MODEL to run this example")
        return 0
    return anyio.run(_run, model_name)


if __name__ == "__main__":
    raise SystemExit(main())
