"""LoopPlane CLI host (feature 017-loopplane-cli-host).

A thin terminal host over the public Host Application Interface
(:mod:`loopplane.host`): the ``loopplane`` console command runs prompts through the
host and renders the run from the normalized event stream. Credential-free by
default (a built-in demo model); a real model is opt-in via ``LOOPPLANE_MODEL``. The
CLI executes no tool and re-emits no event bus (Constitution V/VI), and is additive —
installing the package without invoking the CLI changes nothing.
"""

from __future__ import annotations

import sys

from loopplane.cli.app import build_host, dispatch, make_parser
from loopplane.cli.prompts import LineSource, parse_approval_answer, question_answer
from loopplane.cli.providers import DemoModel, select_model
from loopplane.cli.remote import RemoteEndpoint, remote_loop
from loopplane.cli.render import EventRenderer
from loopplane.cli.session import chat_loop, resume_loop, run_once


def main() -> None:
    """The ``loopplane`` console entry point."""
    raise SystemExit(dispatch(sys.argv[1:]))


__all__ = [
    "DemoModel",
    "EventRenderer",
    "LineSource",
    "RemoteEndpoint",
    "build_host",
    "chat_loop",
    "dispatch",
    "main",
    "make_parser",
    "parse_approval_answer",
    "question_answer",
    "remote_loop",
    "resume_loop",
    "run_once",
    "select_model",
]
