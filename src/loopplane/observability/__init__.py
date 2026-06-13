"""Observability: an optional, strictly metadata-only overlay
(FR-100–FR-104; research R5).

Disabled by default. `maybe_attach` is the env-gated entry point: without an
exporter endpoint configured — or without the optional `otel` extra
installed — it returns the inner sink unchanged, which is the zero-overhead
path (FR-100).
"""

from __future__ import annotations

import os

from loopplane.events.emitter import EventSink

_GATE_VARIABLE = "OTEL_EXPORTER_OTLP_ENDPOINT"


def maybe_attach(inner: EventSink) -> EventSink:
    if not os.environ.get(_GATE_VARIABLE):
        return inner
    try:
        from loopplane.observability.overlay import ObservabilitySink
    except ImportError:
        return inner
    return ObservabilitySink(inner)


__all__ = ["maybe_attach"]
