"""The hook registry: register, unregister, and clear callbacks per lifecycle
point (FR-001, FR-003; contracts/hooks.md).

Owned by the Runtime Controller (one per runtime). Callbacks fire in registration
order (FIFO). ``callbacks`` returns a snapshot tuple so a registration made during
a firing cannot affect that in-flight firing (FR-018).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loopplane.hooks.points import LifecyclePoint

#: A caller-supplied hook. Synchronous or asynchronous (FR-004). For an
#: observational point its return is ignored; for a gating point it returns the
#: point's decision (or abstains by returning ``None`` / an unrecognized value).
HookCallback = Callable[[Any], Any]


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[LifecyclePoint, list[HookCallback]] = {}

    def register(self, point: LifecyclePoint, callback: HookCallback) -> None:
        self._hooks.setdefault(point, []).append(callback)

    def unregister(self, point: LifecyclePoint, callback: HookCallback) -> bool:
        callbacks = self._hooks.get(point)
        if not callbacks:
            return False
        try:
            callbacks.remove(callback)
        except ValueError:
            return False
        return True

    def clear(self, point: LifecyclePoint | None = None) -> None:
        if point is None:
            self._hooks.clear()
        else:
            self._hooks.pop(point, None)

    def callbacks(self, point: LifecyclePoint) -> tuple[HookCallback, ...]:
        """A point's callbacks in registration order, as an immutable snapshot."""
        return tuple(self._hooks.get(point, ()))

    def has(self, point: LifecyclePoint) -> bool:
        return bool(self._hooks.get(point))
