# Contract: Model-Native Structured Output

## `ModelRequest.output_schema` (model boundary)

- Optional field on `loopplane.model.boundary.ModelRequest`: `output_schema: dict[str, object]
  | None = None`.
- When `None`: the assembled provider request is identical to today (no `response_format`).
- When set on an OpenAI-family adapter: the chat-completions call includes
  `response_format = {"type": "json_schema", "json_schema": {"name": "<name>", "schema":
  <output_schema>, "strict": true}}`.

## Capability probe (`loopplane.model.capabilities`)

```python
@runtime_checkable
class StructuredOutputModel(Protocol):
    def supports_structured_output(self) -> bool: ...

def supports_structured_output(model: object) -> bool:
    # model.supports_structured_output() if advertised, else conservative False
```

- Adapter flags: `openai`=True, `openrouter`=True, `ollama`=configurable (default False),
  `anthropic`=False (deferred), `gemini`=False (deferred).

## Web/API behavior

| Case | Result |
| ---- | ------ |
| No `output_schema` in the run request | Unchanged behavior (byte-identical). |
| `output_schema` + selected model supports it | Threaded to `ModelRequest.output_schema`; provider constrained; response should validate against the schema. |
| `output_schema` + selected model does NOT support it | HTTP 400 normalized error (no run started, no falsely-structured output). |
| Malformed `output_schema` | HTTP 400 normalized error at request time, before any model call. |
| `GET /v1/models` | Each model advertises `supports_structured_output`. |

## Verification

- Conformance checked with the unit-005 JSON-schema validator pack (no new engine).

## Invariants

- No `stream_turn` signature change; `ModelBoundary` Protocol unchanged.
- No event-schema / `SCHEMA_VERSION` / content-model change (VI).
- Default `None` path byte-identical to pre-045 (proven by an off-path test).
- Errors are normalized; no leaked schema internals/secrets (VII).
