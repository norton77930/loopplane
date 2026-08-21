"""Desktop in-app provider selection (Unit A).

``select_desktop_model`` gains a configured-provider branch so the packaged app
can reach a real model without the operator exporting ``LOOPPLANE_MODEL``.

Two properties matter more than the happy path:

* every failure degrades to the demo model rather than raising, because the
  sidecar has no operator watching it; and
* the adapters are reached by dynamic import only. ``tests/contract/
  test_desktop_boundary.py`` allows the sidecar to import ``loopplane.host``,
  ``loopplane.events``, ``loopplane.errors`` and ``loopplane.model`` and nothing
  else, so a static ``loopplane.adapters`` import would fail that audit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[2] / "apps" / "desktop" / "sidecar"
sys.path.insert(0, str(SIDECAR))

from bridge import (  # noqa: E402
    DESKTOP_API_KEY_ENV,
    DESKTOP_MODEL_ID_ENV,
    DESKTOP_PROVIDER_ENV,
    DESKTOP_PROVIDERS,
    build_desktop_provider_model,
    select_desktop_model,
)

FAKE_KEY = "sk-unit-a-sample-key-4f2a"


def _env(provider: str, model_id: str, api_key: str | None = None) -> dict[str, str]:
    env = {DESKTOP_PROVIDER_ENV: provider, DESKTOP_MODEL_ID_ENV: model_id}
    if api_key is not None:
        env[DESKTOP_API_KEY_ENV] = api_key
    return env


def _is_demo(model: object) -> bool:
    return type(model).__name__ == "DemoModel"


def _explode(model_id: str, api_key: str | None) -> object:
    """A builder that fails with the credential in its message."""

    raise RuntimeError(f"boom: {api_key}")


class TestProviderTable:
    def test_exposes_the_five_supported_provider_ids(self) -> None:
        assert set(DESKTOP_PROVIDERS) == {
            "anthropic",
            "openai",
            "gemini",
            "openrouter",
            "ollama",
        }

    def test_only_ollama_runs_without_a_key(self) -> None:
        keyless = {
            provider
            for provider, spec in DESKTOP_PROVIDERS.items()
            if not spec.requires_key
        }
        assert keyless == {"ollama"}


class TestBuildProviderModel:
    @pytest.mark.parametrize(
        ("provider", "adapter_name"),
        [
            ("anthropic", "AnthropicModel"),
            ("openai", "OpenAIModel"),
            ("gemini", "GeminiModel"),
            ("openrouter", "OpenAIModel"),
        ],
    )
    def test_builds_the_adapter_and_injects_the_key(
        self, provider: str, adapter_name: str
    ) -> None:
        model = build_desktop_provider_model(provider, "some-model-id", FAKE_KEY)

        assert model is not None
        assert type(model).__name__ == adapter_name
        config = model._config  # noqa: SLF001 - proving the key actually flows
        assert config.model == "some-model-id"
        assert config.api_key == FAKE_KEY

    def test_ollama_builds_without_a_key(self) -> None:
        model = build_desktop_provider_model("ollama", "llama3", None)

        assert model is not None
        assert type(model).__name__ == "OpenAIModel"
        assert model._config.model == "llama3"  # noqa: SLF001

    @pytest.mark.parametrize(
        ("provider", "model_id", "api_key"),
        [
            ("not-a-provider", "m", FAKE_KEY),
            ("", "m", FAKE_KEY),
            ("anthropic", "", FAKE_KEY),
            ("anthropic", "   ", FAKE_KEY),
            ("anthropic", "m", None),
            ("anthropic", "m", ""),
            ("anthropic", "m", "   "),
        ],
    )
    def test_returns_none_for_an_unusable_configuration(
        self, provider: str, model_id: str, api_key: str | None
    ) -> None:
        assert build_desktop_provider_model(provider, model_id, api_key) is None

    def test_an_adapter_that_raises_degrades_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(DESKTOP_PROVIDERS["anthropic"], "build", _explode)

        assert build_desktop_provider_model("anthropic", "m", FAKE_KEY) is None


class TestSelectDesktopModel:
    def test_no_configuration_still_yields_the_demo_model(self) -> None:
        assert _is_demo(select_desktop_model({}))

    def test_a_configured_provider_is_used(self) -> None:
        model = select_desktop_model(_env("anthropic", "claude-x", FAKE_KEY))

        assert type(model).__name__ == "AnthropicModel"

    def test_an_unusable_provider_configuration_falls_back_to_demo(self) -> None:
        assert _is_demo(select_desktop_model(_env("not-a-provider", "m", FAKE_KEY)))

    def test_the_packaged_smoke_scenario_outranks_a_configured_provider(self) -> None:
        env = _env("anthropic", "claude-x", FAKE_KEY)
        env["LOOPPLANE_PACKAGED_SMOKE_SCENARIO"] = "happy"

        model = select_desktop_model(env)

        assert type(model).__name__ == "ScriptedModel"

    def test_the_legacy_builder_reference_still_works(self) -> None:
        model = select_desktop_model(
            {"LOOPPLANE_MODEL": "tests.unit.test_desktop_provider_selection:_builder"}
        )

        assert type(model).__name__ == "ScriptedModel"

    def test_a_configured_provider_outranks_the_legacy_builder_reference(self) -> None:
        env = _env("anthropic", "claude-x", FAKE_KEY)
        env["LOOPPLANE_MODEL"] = "tests.unit.test_desktop_provider_selection:_builder"

        model = select_desktop_model(env)

        assert type(model).__name__ == "AnthropicModel"

    def test_selection_never_raises_and_never_echoes_the_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(DESKTOP_PROVIDERS["anthropic"], "build", _explode)

        model = select_desktop_model(_env("anthropic", "claude-x", FAKE_KEY))

        assert _is_demo(model)
        assert FAKE_KEY not in repr(model)


def test_the_launch_path_drops_the_key_from_the_environment() -> None:
    """Whatever this process spawns later must not inherit the credential."""

    source = (SIDECAR / "bridge.py").read_text(encoding="utf-8")
    select_at = source.index("model = select_desktop_model(os.environ)")
    pop_at = source.index("os.environ.pop(DESKTOP_API_KEY_ENV, None)")

    assert select_at < pop_at
    # The scrub happens before the Host exists, so nothing the runtime later
    # launches can have inherited it.
    assert pop_at < source.index("bootstrap_desktop_owner(profile)")


def _builder() -> object:
    """A ``module:attr`` target for the legacy ``LOOPPLANE_MODEL`` path."""

    from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="legacy")])],
        context_capacity=1000,
    )
