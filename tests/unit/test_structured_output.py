"""Unit 045: model-native structured output. Deterministic and offline.

Covers the additive `ModelRequest.output_schema` field mapped to the OpenAI
`response_format` json_schema, the duck-typed `supports_structured_output` probe +
per-adapter flags, end-to-end threading from the web/API edge to the model request,
graceful degradation (a schema for a non-supporting model is a 400; a malformed
schema is a 400), the catalog advertising the capability, and verification reusing
the unit-005 JSON-schema validator pack.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from loopplane.adapters.openai import OpenAIConfig, OpenAIModel  # noqa: E402
from loopplane.adapters.openai_compat import (  # noqa: E402
    ollama_model,
    openrouter_model,
)
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig  # noqa: E402
from loopplane.model import supports_structured_output  # noqa: E402
from loopplane.model.boundary import (  # noqa: E402
    Message,
    ModelIncrement,
    ModelRequest,
    TextIncrement,
    TokenUsage,
    TurnEnd,
)
from loopplane.model.content import TextBlock  # noqa: E402
from loopplane.packs import json_schema_validator  # noqa: E402
from loopplane.webapi import create_app  # noqa: E402
from loopplane.webapi.app import ModelHost  # noqa: E402
from tests.integration.provider_stubs import make_model  # noqa: E402
from tests.packs_helpers import SAMPLE_SCHEMA, scripted_outcome  # noqa: E402
from tests.webapi_helpers import allow_all, make_client  # noqa: E402

_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


# --- US1: the OpenAI adapter maps output_schema to response_format ------------


@pytest.mark.anyio
async def test_openai_adapter_sets_response_format_when_schema_present() -> None:
    model, client = make_model("openai", [("text", "ok")])
    request = ModelRequest(
        context=[Message(role="user", blocks=[TextBlock(text="hi")])],
        output_schema=_SCHEMA,
    )

    async for _ in model.stream_turn(request):
        pass

    response_format = client.calls[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == _SCHEMA
    assert response_format["json_schema"]["strict"] is True


@pytest.mark.anyio
async def test_openai_adapter_omits_response_format_when_no_schema() -> None:
    model, client = make_model("openai", [("text", "ok")])
    request = ModelRequest(
        context=[Message(role="user", blocks=[TextBlock(text="hi")])]
    )

    async for _ in model.stream_turn(request):
        pass

    assert "response_format" not in client.calls[0]


# --- US2 / capability: the duck-typed probe + per-adapter flags ---------------


class _Structured:
    def supports_structured_output(self) -> bool:
        return True


class _Unstructured:
    def supports_structured_output(self) -> bool:
        return False


class _NoSignal:
    """A model that does not advertise structured-output support at all."""


def test_probe_reads_a_true_signal() -> None:
    assert supports_structured_output(_Structured()) is True


def test_probe_reads_a_false_signal() -> None:
    assert supports_structured_output(_Unstructured()) is False


def test_probe_defaults_false_when_absent() -> None:
    assert supports_structured_output(_NoSignal()) is False


def test_openai_config_default_supports_structured_output() -> None:
    model = OpenAIModel(OpenAIConfig(model="gpt", client=object()))
    assert model.supports_structured_output() is True
    assert supports_structured_output(model) is True

    off = OpenAIModel(
        OpenAIConfig(model="gpt", client=object(), supports_structured_output=False)
    )
    assert supports_structured_output(off) is False


def test_openai_compat_structured_output_defaults() -> None:
    # OpenRouter brokers OpenAI-wire models that support response_format -> True.
    assert supports_structured_output(openrouter_model("x", client=object())) is True
    # Local Ollama support varies, so the default is False (operator opts in).
    assert supports_structured_output(ollama_model("x", client=object())) is False
    assert (
        supports_structured_output(
            ollama_model("x", client=object(), supports_structured_output=True)
        )
        is True
    )


# --- US1: end-to-end threading from the web/API edge to the model request -----


class RecordingModel:
    """Records the last `ModelRequest` it streamed and emits one closing turn."""

    def __init__(self) -> None:
        self.last_request: ModelRequest | None = None

    def context_capacity(self) -> int:
        return 100_000

    def accepts_media(self) -> bool:
        return True

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        self.last_request = request
        yield TextIncrement(text="ok")
        yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())


def _host(root: Path, model: RecordingModel) -> LoopPlaneHost:
    root.mkdir(parents=True, exist_ok=True)
    return LoopPlaneHost(
        RuntimeConfig(model=model, tools=(), storage=StorageConfig(root=root)),
        working_scope=root,
    )


def test_schema_reaches_the_model_request(tmp_path: Path) -> None:
    model = RecordingModel()
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            default_supports_structured_output=True,
        )
    )

    run = client.post("/v1/runs", json={"prompt": "hi", "output_schema": _SCHEMA})

    assert run.status_code == 200
    assert model.last_request is not None
    assert model.last_request.output_schema == _SCHEMA


def test_no_schema_is_none_on_the_model_request(tmp_path: Path) -> None:
    model = RecordingModel()
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            default_supports_structured_output=True,
        )
    )

    run = client.post("/v1/runs", json={"prompt": "hi"})

    assert run.status_code == 200
    assert model.last_request is not None
    assert model.last_request.output_schema is None


# --- US2: graceful degradation + catalog -------------------------------------


def test_schema_on_nonsupporting_model_is_rejected(tmp_path: Path) -> None:
    model = RecordingModel()
    client = make_client(
        create_app(_host(tmp_path / "store", model), authenticator=allow_all)
    )  # default_supports_structured_output defaults False

    run = client.post("/v1/runs", json={"prompt": "hi", "output_schema": _SCHEMA})

    assert run.status_code == 400
    assert model.last_request is None  # no run started


def test_malformed_schema_is_rejected(tmp_path: Path) -> None:
    model = RecordingModel()
    client = make_client(
        create_app(
            _host(tmp_path / "store", model),
            authenticator=allow_all,
            default_supports_structured_output=True,
        )
    )

    run = client.post("/v1/runs", json={"prompt": "hi", "output_schema": {}})

    assert run.status_code == 400
    assert model.last_request is None


def test_catalog_advertises_supports_structured_output(tmp_path: Path) -> None:
    shared = tmp_path / "store"
    structured = _host(shared, RecordingModel())
    plain = _host(shared, RecordingModel())
    models = {
        "structured": ModelHost(
            label="Structured", host=structured, supports_structured_output=True
        ),
        "plain": ModelHost(label="Plain", host=plain, supports_structured_output=False),
    }
    client = make_client(create_app(structured, authenticator=allow_all, models=models))

    listing = client.get("/v1/models")

    assert listing.status_code == 200
    by_id = {m["id"]: m for m in listing.json()}
    assert by_id["structured"]["supports_structured_output"] is True
    assert by_id["plain"]["supports_structured_output"] is False


# --- US3: verification reuses the unit-005 JSON-schema validator pack ---------


def test_structured_output_verifiable_via_packs_validator() -> None:
    validator = json_schema_validator(schema=SAMPLE_SCHEMA)

    ok_outcome, ok_state = scripted_outcome(text='{"ok": true}')
    assert validator(ok_outcome, ok_state).status == "pass"

    bad_outcome, bad_state = scripted_outcome(text='{"ok": "not a boolean"}')
    assert validator(bad_outcome, bad_state).status == "fail"
