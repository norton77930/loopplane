"""LoopPlane Web / API Host (feature 011-loopplane-web-api-host).

An additive transport that exposes the public Host Application Interface
(:mod:`loopplane.host`) over a network API: request/response endpoints, a
Server-Sent-Events stream of the run's normalized events, an injectable
default-deny authentication boundary, and read-only inspection. It embeds a
``LoopPlaneHost``; it drives no runtime internals, executes no tool, and never
re-emits the live event bus (Constitution V & VI).

This package requires the ``web`` extra (``pip install loopplane[web]``).
"""

from __future__ import annotations

from loopplane.webapi.app import create_app
from loopplane.webapi.auth import Authenticator, Principal, token_authenticator
from loopplane.webapi.auth_jwt import jwt_authenticator
from loopplane.webapi.models import (
    ArtifactContent,
    ErrorResponse,
    HistoryEntryView,
    OpenedSession,
    QuestionAnswer,
    Resolved,
    RunRequest,
    RunResult,
    SessionAnswer,
    SessionSummaryView,
    UploadRef,
)

__all__ = [
    "ArtifactContent",
    "Authenticator",
    "ErrorResponse",
    "HistoryEntryView",
    "OpenedSession",
    "Principal",
    "QuestionAnswer",
    "Resolved",
    "RunRequest",
    "RunResult",
    "SessionAnswer",
    "SessionSummaryView",
    "UploadRef",
    "create_app",
    "jwt_authenticator",
    "token_authenticator",
]
