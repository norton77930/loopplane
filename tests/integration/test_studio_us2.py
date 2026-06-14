"""US2: manage local sessions — open / list / select / close (FR-010/011,
FR-003). In-process only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.studio import ErrorView, StudioHost
from tests.studio_helpers import build_test_host, multi_text_model


@pytest.mark.anyio
async def test_open_list_select_cancel(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    async with StudioHost(host) as studio:
        session_id = await studio.open_session()
        assert isinstance(session_id, str)

        assert session_id in [s.session_id for s in studio.list_sessions()]
        assert studio.select(session_id) == session_id
        assert isinstance(studio.select("ghost"), ErrorView)

        assert await studio.cancel(session_id) is None
        assert isinstance(await studio.cancel("ghost"), ErrorView)


@pytest.mark.anyio
async def test_second_open_while_active_conflicts(tmp_path: Path) -> None:
    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    async with StudioHost(host) as studio:
        session_id = await studio.open_session()
        assert isinstance(session_id, str)

        conflict = await studio.open_session()
        assert isinstance(conflict, ErrorView)
        assert conflict.kind == "conflict"

        await studio.cancel(session_id)
