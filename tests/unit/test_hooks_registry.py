"""Unit tests for the hook registry (T004; FR-001, FR-003, FR-018)."""

from __future__ import annotations

from loopplane.hooks import HookRegistry, LifecyclePoint

POINT = LifecyclePoint.after_tool_use


def _cb(_payload: object) -> None:
    return None


def test_register_appends_in_order() -> None:
    registry = HookRegistry()

    def a(_p: object) -> None: ...
    def b(_p: object) -> None: ...

    registry.register(POINT, a)
    registry.register(POINT, b)
    assert registry.callbacks(POINT) == (a, b)
    assert registry.has(POINT)


def test_duplicate_registration_fires_twice() -> None:
    registry = HookRegistry()
    registry.register(POINT, _cb)
    registry.register(POINT, _cb)
    assert registry.callbacks(POINT) == (_cb, _cb)


def test_unregister_removes_first_match_and_reports() -> None:
    registry = HookRegistry()
    registry.register(POINT, _cb)
    assert registry.unregister(POINT, _cb) is True
    assert registry.callbacks(POINT) == ()
    assert registry.unregister(POINT, _cb) is False


def test_clear_point_then_all() -> None:
    registry = HookRegistry()
    registry.register(POINT, _cb)
    registry.register(LifecyclePoint.model_stop, _cb)
    registry.clear(POINT)
    assert not registry.has(POINT)
    assert registry.has(LifecyclePoint.model_stop)
    registry.clear()
    assert not registry.has(LifecyclePoint.model_stop)


def test_callbacks_snapshot_is_immutable() -> None:
    registry = HookRegistry()
    registry.register(POINT, _cb)
    snapshot = registry.callbacks(POINT)
    registry.register(POINT, _cb)  # mutate after snapshot
    assert snapshot == (_cb,)  # the earlier snapshot is unaffected (FR-018)
