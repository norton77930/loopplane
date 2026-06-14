"""Unit tests for CLI provider selection (T003; FR-005, FR-006)."""

from __future__ import annotations

from loopplane.cli.providers import DemoModel, select_model
from loopplane.model import ModelBoundary, ScriptedModel


def test_no_env_selects_the_demo_model() -> None:
    model = select_model({})
    assert isinstance(model, DemoModel)
    assert isinstance(model, ModelBoundary)


def test_env_builder_is_imported_and_used() -> None:
    model = select_model({"LOOPPLANE_MODEL": "tests.cli_helpers:build_fake_model"})
    assert isinstance(model, ScriptedModel)


def test_bad_reference_falls_back_to_the_demo_model() -> None:
    assert isinstance(
        select_model({"LOOPPLANE_MODEL": "no.such.module:thing"}), DemoModel
    )
    assert isinstance(select_model({"LOOPPLANE_MODEL": "no-colon-here"}), DemoModel)
