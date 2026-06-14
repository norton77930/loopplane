"""The CLI run core over the Host Application Interface (spec FR-002, FR-003).

``run_once`` and ``chat_loop`` are the testable core: they take a host, the input,
and an output stream, so the whole CLI is exercised with a scripted model and
captured streams. The interactive REPL (in ``app``) is a thin wrapper that feeds
real stdin lines into ``chat_loop``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TextIO

from loopplane.cli.render import EventRenderer
from loopplane.host import LoopPlaneHost, RunOutcome


async def run_once(host: LoopPlaneHost, prompt: str, out: TextIO) -> RunOutcome:
    """Run one prompt and render it to ``out``; returns the run outcome."""
    return await host.run(prompt, EventRenderer(out))


async def chat_loop(host: LoopPlaneHost, lines: Iterable[str], out: TextIO) -> None:
    """Run each input line as a turn until EOF or a ``quit``/``exit`` line."""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        await run_once(host, line, out)
