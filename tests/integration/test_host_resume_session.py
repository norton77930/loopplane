"""078 T016/T021/T022: resume_session and working_scope seams."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig

from .conftest import EventCollector, text_model

pytestmark = pytest.mark.anyio


async def test_resume_session_interactive_round_trip(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store",
            ),
        ),
        working_scope=tmp_path,
    )
    sink1 = EventCollector()
    async with host.session(sink1) as session:
        await session.submit("hello")
        session_id = session.session_id
        _ = session.outcome()

    sink2 = EventCollector()
    async with host.resume_session(
        session_id, sink2, working_scope=tmp_path
    ) as session:
        assert session.session_id == session_id
        await session.submit("again")
        out = session.outcome()
        assert out.session_id == session_id


async def test_controller_resume_working_scope_optional(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=text_model(),
            storage=StorageConfig(
                checkpoint_backend="sqlite",
                root=tmp_path / "store2",
            ),
        ),
        working_scope=tmp_path,
    )
    sink = EventCollector()
    async with host.session(sink) as session:
        await session.submit("x")
        sid = session.session_id
        _ = session.outcome()

    # Default-preserving: no working_scope kwarg
    await host.resume(sid)
    # Explicit scope
    await host.resume(sid, working_scope=tmp_path)
