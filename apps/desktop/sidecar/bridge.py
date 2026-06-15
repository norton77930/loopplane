"""Serverless stdio NDJSON bridge over ``loopplane.host`` (feature 019).

The desktop app spawns this as a local sidecar: it drives a ``LoopPlaneHost`` and
writes each normalized event as one JSON line (the unit-011 ``serialize_event``),
followed by an ``outcome`` line — with no HTTP server and no port. It runs no tool
itself and re-emits no bus; it is a streaming consumer of the normalized stream
(Constitution V/VI). It reuses only ``loopplane.host`` + ``loopplane.events`` and is
loaded by file path in tests, so it adds no package and is not shipped in the wheel.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from loopplane.events import RuntimeEvent, serialize_event
from loopplane.host import LoopPlaneHost

ReadLine = Callable[[], Awaitable[str | None]]
WriteLine = Callable[[str], None]


async def collect_events(host: LoopPlaneHost, prompt: str) -> list[str]:
    """Drive one run; return the serialized event lines plus an outcome line.

    The testable core: each normalized event becomes one ``serialize_event`` line,
    and the run's terminal outcome is the final line.
    """
    lines: list[str] = []

    async def sink(event: RuntimeEvent) -> None:
        lines.append(serialize_event(event))

    outcome = await host.run(prompt, sink)
    lines.append(
        json.dumps(
            {
                "op": "outcome",
                "reason": outcome.termination_reason,
                "turns": outcome.turns_taken,
            }
        )
    )
    return lines


async def serve(
    host: LoopPlaneHost, read_line: ReadLine, write_line: WriteLine
) -> None:
    """The stdio loop: read request lines, drive runs, write event + outcome lines.

    ``read_line`` returns ``None`` at end-of-input. Injectable I/O keeps the loop
    testable; ``main`` wires it to real stdio.
    """
    while True:
        line = await read_line()
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (ValueError, TypeError):
            write_line(json.dumps({"op": "error", "detail": "malformed request"}))
            continue
        if request.get("op") == "run":
            await _run(host, str(request.get("prompt", "")), write_line)


async def _run(host: LoopPlaneHost, prompt: str, write_line: WriteLine) -> None:
    async def sink(event: RuntimeEvent) -> None:
        write_line(serialize_event(event))

    try:
        outcome = await host.run(prompt, sink)
    except RuntimeError:
        write_line(json.dumps({"op": "error", "detail": "a run is already active"}))
        return
    write_line(
        json.dumps(
            {
                "op": "outcome",
                "reason": outcome.termination_reason,
                "turns": outcome.turns_taken,
            }
        )
    )


def main() -> None:  # pragma: no cover - the real stdio entry point (manual smoke)
    import sys

    import anyio

    from loopplane.host import RuntimeConfig
    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

    # A credential-free default host; a real model is wired by the shell/operator.
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="LoopPlane desktop demo")])
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(RuntimeConfig(model=model))

    async def read_line() -> str | None:
        return await anyio.to_thread.run_sync(sys.stdin.readline) or None

    def write_line(text: str) -> None:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    anyio.run(serve, host, read_line, write_line)


if __name__ == "__main__":  # pragma: no cover
    main()
