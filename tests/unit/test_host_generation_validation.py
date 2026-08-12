"""Host validate_active_generation facade tests (078 T018/T025)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loopplane.host import (
    GenerationExpectation,
    validate_active_generation,
)


def test_pristine_absence_with_default_provider() -> None:
    result = validate_active_generation(
        {},
        GenerationExpectation(
            checkpoint_state="absent_uninitialized",
            artifact_state="absent_uninitialized",
        ),
    )
    assert result.ok is True
    assert result.checkpoint_state == "absent_uninitialized"
    assert result.artifact_state == "absent_uninitialized"


def test_initialized_expectation_match() -> None:
    result = validate_active_generation(
        {
            "checkpoint_state": "initialized",
            "artifact_state": "initialized",
            "schema_version": 1,
        },
        GenerationExpectation(
            checkpoint_state="initialized",
            artifact_state="initialized",
            schema_version=1,
        ),
    )
    assert result.ok is True


def test_expectation_mismatch() -> None:
    result = validate_active_generation(
        {"checkpoint_state": "initialized", "artifact_state": "initialized"},
        GenerationExpectation(
            checkpoint_state="absent_uninitialized",
            artifact_state="absent_uninitialized",
        ),
    )
    assert result.ok is False
    assert result.reason == "expectation_mismatch"


def test_unexpected_payload() -> None:
    result = validate_active_generation(
        {"unexpected": True},
        GenerationExpectation(),
    )
    assert result.ok is False
    assert result.reason == "unexpected_payload"


def test_provider_fault_is_contained() -> None:
    class Boom:
        def probe(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
            raise RuntimeError("secret")

    result = validate_active_generation({}, GenerationExpectation(), provider=Boom())
    assert result.ok is False
    assert result.reason == "provider_fault:RuntimeError"


def test_zero_host_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validator must not import/construct LoopPlaneHost."""

    import loopplane.host.host as host_mod

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("LoopPlaneHost must not be constructed")

    monkeypatch.setattr(host_mod, "LoopPlaneHost", boom)
    result = validate_active_generation({}, GenerationExpectation())
    assert result.ok is True


@pytest.mark.parametrize(
    ("checkpoint_state", "artifact_state"),
    [
        ("initialized", "initialized"),
        ("absent_uninitialized", "absent_uninitialized"),
    ],
)
def test_injected_startup_probe_is_read_only_and_constructs_no_host_or_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkpoint_state: str,
    artifact_state: str,
) -> None:
    """T070: the Host facade validates state, not pointer/proof lineage."""

    import loopplane.artifacts.store as artifact_module
    import loopplane.checkpoint.sqlite as sqlite_module
    import loopplane.host.host as host_mod

    root = tmp_path / "generation"
    root.mkdir()
    sentinel = root / "sentinel.bin"
    sentinel.write_bytes(b"unchanged")
    before = sorted(path.relative_to(root) for path in root.rglob("*"))

    def forbid_construction(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "startup validation must not construct Host or normal stores"
        )

    class ReadOnlyProbe:
        def probe(self, source: Mapping[str, Any]) -> Mapping[str, Any]:
            assert source == {"generation_root": str(root)}
            return {
                "checkpoint_state": checkpoint_state,
                "artifact_state": artifact_state,
                "schema_version": 1,
            }

    monkeypatch.setattr(host_mod, "LoopPlaneHost", forbid_construction)
    monkeypatch.setattr(sqlite_module, "SqliteCheckpointStore", forbid_construction)
    monkeypatch.setattr(artifact_module, "ArtifactStore", forbid_construction)
    result = validate_active_generation(
        {"generation_root": str(root)},
        GenerationExpectation(
            checkpoint_state=checkpoint_state,  # type: ignore[arg-type]
            artifact_state=artifact_state,  # type: ignore[arg-type]
            schema_version=1,
        ),
        provider=ReadOnlyProbe(),
    )

    assert result.ok is True
    assert sentinel.read_bytes() == b"unchanged"
    assert sorted(path.relative_to(root) for path in root.rglob("*")) == before
