"""Desktop sidecar host commands (083 Wave 6, T032/T033; ADR 0017).

A leading ``/`` is answered by the shared ``CommandRegistry`` against public
host seams only — no model call, no Gateway invocation, no Event Bus emission.
The fake host below exposes exactly the four seams the registry may read, so
any other reach is an ``AttributeError``, and dispatch failures degrade to the
registry's fixed public text (FR-013, FR-014, FR-016–FR-018).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.helpers.public_safety import all_prohibited_secondary_markers

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from methods.command import CommandMethods  # noqa: E402
from mutation_lease import ProfileMutationLease  # noqa: E402
from protocol import RpcError  # noqa: E402

pytestmark = pytest.mark.anyio

POISON_TEXT = " | ".join(all_prohibited_secondary_markers())


class _FakeHost:
    """Exactly the registry's four seams plus session ownership — nothing else."""

    def __init__(self) -> None:
        self.compacted: list[str] = []
        self.monthly_error = False

    def list_sessions(self) -> tuple[Any, ...]:
        return (SimpleNamespace(session_id="s-1", principal_id="principal-1"),)

    def session_cost(self, session_id: str) -> Decimal | None:
        return Decimal("0.25")

    def monthly_spend(self, principal_id: str) -> Decimal | None:
        if self.monthly_error:
            raise RuntimeError(POISON_TEXT)
        return Decimal("12.50")

    def inspect_memory(self, query: str | None = None) -> tuple[Any, ...]:
        return (SimpleNamespace(name="prefs", snippet="dark theme"),)

    def compact_session(self, session_id: str) -> bool:
        self.compacted.append(session_id)
        return True


def _methods(
    host: _FakeHost | None = None,
    lease: ProfileMutationLease | None = None,
    configured_model_id: str | None = "model-x",
) -> CommandMethods:
    return CommandMethods(
        host or _FakeHost(),  # type: ignore[arg-type]
        principal_provider=lambda: "principal-1",
        mutation_lease=lease,
        configured_model_id=configured_model_id,
    )


async def test_cost_command_answers_from_host_seams() -> None:
    result = await _methods().execute(
        {"mutation_id": "m-1", "text": "/cost", "session_id": "s-1"}
    )
    assert result["kind"] == "ok"
    assert "session: 0.25" in result["text"]
    assert "monthly: 12.50" in result["text"]


async def test_model_command_lists_the_configured_model() -> None:
    listed = await _methods().execute({"mutation_id": "m-2", "text": "/model"})
    assert listed["kind"] == "ok"
    assert "model-x" in listed["text"]
    none_configured = await _methods(configured_model_id=None).execute(
        {"mutation_id": "m-3", "text": "/model"}
    )
    assert "none advertised" in none_configured["text"]


async def test_memory_and_compact_commands() -> None:
    host = _FakeHost()
    memory = await _methods(host).execute({"mutation_id": "m-4", "text": "/memory"})
    assert "prefs" in memory["text"]

    compacted = await _methods(host).execute(
        {"mutation_id": "m-5", "text": "/compact", "session_id": "s-1"}
    )
    assert compacted == {"kind": "ok", "text": "compacted"}
    assert host.compacted == ["s-1"]

    no_session = await _methods(host).execute(
        {"mutation_id": "m-6", "text": "/compact"}
    )
    assert no_session["kind"] == "error"


async def test_unknown_command_answers_the_normalized_message() -> None:
    result = await _methods().execute({"mutation_id": "m-7", "text": "/frobnicate"})
    assert result == {"kind": "unknown", "text": "unknown command: /frobnicate"}


async def test_mutation_id_required_and_busy_lease_refused() -> None:
    with pytest.raises(RpcError) as exc:
        await _methods().execute({"text": "/cost"})
    assert exc.value.category == "invalid_params"

    lease = ProfileMutationLease()
    lease.acquire("backup", "other-op")
    with pytest.raises(RpcError) as busy:
        await _methods(lease=lease).execute({"mutation_id": "m-8", "text": "/cost"})
    assert busy.value.category == "busy"


async def test_unowned_session_is_not_found() -> None:
    with pytest.raises(RpcError) as exc:
        await _methods().execute(
            {"mutation_id": "m-9", "text": "/cost", "session_id": "s-404"}
        )
    assert exc.value.category == "not_found"


async def test_failing_seam_degrades_to_fixed_public_text() -> None:
    host = _FakeHost()
    host.monthly_error = True
    lease = ProfileMutationLease()
    result = await _methods(host, lease).execute(
        {"mutation_id": "m-10", "text": "/cost"}
    )
    assert result == {"kind": "error", "text": "/cost: command failed"}
    assert "hidden" not in str(result) and "sk-live-key" not in str(result)
    assert not lease.held()
