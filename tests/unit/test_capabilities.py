"""Unit 036: the additive, duck-typed model-media capability probe.

`accepts_media(model)` reads `model.accepts_media()` when present, else returns a
conservative `False`. The `ModelBoundary` Protocol is UNCHANGED (still two
methods), so a non-advertising model (e.g. `ScriptedModel`) is treated as
text-only until it opts in.
"""

from __future__ import annotations

from loopplane.model import ScriptedModel, accepts_media


class _Vision:
    def accepts_media(self) -> bool:
        return True


class _TextOnly:
    def accepts_media(self) -> bool:
        return False


class _NoSignal:
    """A model that does not advertise media support at all."""


def test_probe_reads_a_true_signal() -> None:
    assert accepts_media(_Vision()) is True


def test_probe_reads_a_false_signal() -> None:
    assert accepts_media(_TextOnly()) is False


def test_probe_defaults_false_when_absent() -> None:
    assert accepts_media(_NoSignal()) is False


def test_scripted_model_is_text_only_by_default() -> None:
    model = ScriptedModel(script=[], context_capacity=1000)
    assert accepts_media(model) is False


def test_anthropic_adapter_accepts_media_by_default() -> None:
    from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel

    model = AnthropicModel(AnthropicConfig(model="claude", client=object()))
    assert model.accepts_media() is True
    assert accepts_media(model) is True

    text_only = AnthropicModel(
        AnthropicConfig(model="claude", client=object(), accepts_media=False)
    )
    assert accepts_media(text_only) is False


def test_openai_adapter_accepts_media_by_default() -> None:
    from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

    model = OpenAIModel(OpenAIConfig(model="gpt", client=object()))
    assert model.accepts_media() is True
    assert accepts_media(model) is True

    text_only = OpenAIModel(
        OpenAIConfig(model="gpt", client=object(), accepts_media=False)
    )
    assert accepts_media(text_only) is False


def test_gemini_adapter_accepts_media_by_default() -> None:
    from loopplane.adapters.gemini import GeminiConfig, GeminiModel

    model = GeminiModel(GeminiConfig(model="gemini", client=object()))
    assert model.accepts_media() is True
    assert accepts_media(model) is True

    text_only = GeminiModel(
        GeminiConfig(model="gemini", client=object(), accepts_media=False)
    )
    assert accepts_media(text_only) is False


def test_openai_compat_defaults() -> None:
    from loopplane.adapters.openai_compat import ollama_model, openrouter_model

    # OpenRouter brokers vision models -> default True.
    assert accepts_media(openrouter_model("x", client=object())) is True
    # Local Ollama models are commonly text-only -> default False (operator opts in).
    assert accepts_media(ollama_model("x", client=object())) is False
    assert accepts_media(ollama_model("x", client=object(), accepts_media=True)) is True
