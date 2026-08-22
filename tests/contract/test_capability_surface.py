"""Capability surface snapshot (082 T032).

`CapabilityManager` is a 1600-line class that unit 082 decomposes into per-domain
modules. A refactor of that size cannot be verified by reading the diff: a method
that quietly changes shape, loses a keyword-only marker, or stops being a
coroutine looks exactly like a method that moved file.

So the surface is recorded BEFORE the split and compared after. The fixture's
discriminating power comes entirely from having been captured first -- a
snapshot generated from the post-split tree would only restate whatever the
split produced, and would pass no matter what the split broke.

`LoopPlaneHost` is included as well as `CapabilityManager`, because it is the
surface that is actually public (`CapabilityManager` is not in
`loopplane.host.__all__`, but `AssembledRuntime` is, and it carries one).

Reads the committed tree only.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from loopplane.host import LoopPlaneHost
from loopplane.host.capability_manager import CapabilityManager

FIXTURE = Path(__file__).parent / "fixtures" / "capability_surface.json"

_CLASSES: dict[str, type] = {
    "CapabilityManager": CapabilityManager,
    "LoopPlaneHost": LoopPlaneHost,
}


def current_surface() -> dict[str, dict[str, dict[str, Any]]]:
    """The public callable surface of each pinned class, as recorded."""

    surface: dict[str, dict[str, dict[str, Any]]] = {}
    for label, cls in _CLASSES.items():
        members: dict[str, dict[str, Any]] = {}
        for name, value in inspect.getmembers(cls, callable):
            if name.startswith("_"):
                continue
            members[name] = {
                "async": inspect.iscoroutinefunction(value),
                "signature": str(inspect.signature(value)),
            }
        surface[label] = members
    return surface


def _recorded() -> dict[str, dict[str, dict[str, Any]]]:
    assert FIXTURE.is_file(), (
        f"{FIXTURE.name} is missing; the snapshot must be captured from the "
        "pre-refactor tree, never regenerated from the tree it is meant to check"
    )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_no_capability_method_is_added_or_removed() -> None:
    recorded = _recorded()
    current = current_surface()
    assert set(recorded) == set(current), (set(recorded), set(current))
    for label in sorted(recorded):
        expected = set(recorded[label])
        actual = set(current[label])
        assert expected == actual, (
            f"{label} surface drifted: "
            f"removed={sorted(expected - actual)} added={sorted(actual - expected)}"
        )


def test_no_capability_method_changes_shape() -> None:
    """Signature and coroutine-ness are part of the contract, not decoration.

    A caller that awaits a method which silently became synchronous, or passes a
    positional argument to one that silently became keyword-only, breaks at run
    time rather than at import time.
    """

    recorded = _recorded()
    current = current_surface()
    drift: list[str] = []
    for label in sorted(recorded):
        for name in sorted(set(recorded[label]) & set(current[label])):
            was, now = recorded[label][name], current[label][name]
            if was["async"] != now["async"]:
                drift.append(
                    f"{label}.{name}: async {was['async']} -> {now['async']}"
                )
            if was["signature"] != now["signature"]:
                drift.append(
                    f"{label}.{name}: {was['signature']} -> {now['signature']}"
                )
    assert not drift, "capability surface changed shape:\n  " + "\n  ".join(drift)
