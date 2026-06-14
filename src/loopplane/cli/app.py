"""The CLI parser and command dispatch (spec FR-001-FR-003, FR-007, FR-011, FR-012).

``dispatch`` parses argv, builds a host over the public Host Application Interface,
and runs the selected command via ``anyio.run``. The CLI executes no tool and
re-emits no bus — it only renders the normalized event stream (Constitution V/VI).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TextIO

import anyio

from loopplane.cli.providers import select_model
from loopplane.cli.session import chat_loop, run_once
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig


def build_host(store: str | None = None) -> LoopPlaneHost:
    """A host over the selected model, optionally with a durable session store."""
    storage = StorageConfig(root=Path(store)) if store else None
    return LoopPlaneHost(RuntimeConfig(model=select_model(os.environ), storage=storage))


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loopplane", description="Run the LoopPlane agent from the terminal."
    )
    parser.add_argument("--store", help="a directory for durable sessions")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chat", help="hold an interactive chat")
    run_parser = sub.add_parser("run", help="run one prompt and exit")
    run_parser.add_argument("prompt", help="the prompt to run")
    sub.add_parser("sessions", help="list durable sessions")
    resume_parser = sub.add_parser("resume", help="resume a durable session")
    resume_parser.add_argument("session_id", help="the session to resume")
    return parser


def _stdin_lines(out: TextIO) -> Iterator[str]:
    """Prompt-and-read real stdin lines; EOF / Ctrl-C end cleanly (FR-011)."""
    while True:
        out.write("> ")
        out.flush()
        try:
            yield input()
        except (EOFError, KeyboardInterrupt):
            out.write("\n")
            return


async def _run(args: argparse.Namespace, out: TextIO) -> int:
    if args.command == "run":
        await run_once(build_host(args.store), args.prompt, out)
        return 0
    if args.command == "chat":
        await chat_loop(build_host(args.store), _stdin_lines(out), out)
        return 0
    if args.command == "sessions":
        summaries = build_host(args.store).list_sessions()
        if not summaries:
            out.write("no durable sessions (configure --store)\n")
        for summary in summaries:
            out.write(f"{summary.session_id}  {summary.last_active_at.isoformat()}\n")
        return 0
    if args.command == "resume":
        host = build_host(args.store)
        try:
            await host.resume(args.session_id)
        except (KeyError, RuntimeError):
            out.write("could not resume (use --store and a valid session id)\n")
            return 1
        entries = host.history_snapshot(args.session_id)
        out.write(f"resumed {args.session_id} ({len(entries)} history entries)\n")
        return 0
    return 2


def dispatch(argv: Sequence[str], out: TextIO | None = None) -> int:
    """Parse ``argv`` and run the command; returns a process exit code."""
    stream = out if out is not None else sys.stdout
    args = make_parser().parse_args(list(argv))
    if args.command is None:
        make_parser().print_help(stream)
        return 2
    return anyio.run(_run, args, stream)
