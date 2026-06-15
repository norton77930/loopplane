"""Shared model-provider adapter error and a public-safe error-text helper (020).

A provider or transport fault raised by a model-provider adapter. Its message is
public-safe: it carries no credential and no raw response body — only a short summary.
The Agent Loop already terminates the run as ``unrecoverable-error`` and emits no raw
text, so this type exists for clarity and testability, not to cross the event bus.
"""

from __future__ import annotations


class ModelProviderError(Exception):
    """A provider/transport fault with a public-safe message."""


def error_text(exc: BaseException) -> str:
    """A best-effort, read-only summary of a provider exception for matching only.

    Never placed in a caller-visible message; used solely to classify an error (e.g.
    to detect a context-overflow signal).
    """

    message = getattr(exc, "message", None)
    if isinstance(message, str):
        return message
    return str(exc)
