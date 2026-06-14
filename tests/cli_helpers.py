"""Deterministic, public-safe helpers for the CLI host suites (feature 017).

Includes an importable model builder (`tests.cli_helpers:build_fake_model`) for the
`LOOPPLANE_MODEL` provider-selection seam.
"""

from __future__ import annotations

from pathlib import Path

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement


def scripted_host(*texts: str, store: Path | None = None) -> LoopPlaneHost:
    """A host over a scripted model with one text turn per argument."""
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=t)]) for t in texts],
        context_capacity=100_000,
    )
    storage = StorageConfig(root=store) if store is not None else None
    return LoopPlaneHost(RuntimeConfig(model=model, storage=storage))


def build_fake_model() -> ScriptedModel:
    """A model builder the provider seam imports (LOOPPLANE_MODEL=module:function)."""
    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="from a real builder")])],
        context_capacity=100_000,
    )
