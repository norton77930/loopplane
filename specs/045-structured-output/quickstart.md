# Quickstart / Validation: Model-Native Structured Output

See [contracts/structured-output.md](contracts/structured-output.md) and
[data-model.md](data-model.md) for details.

## Prerequisites

- Dev env (`pip install -e .[dev]`); the `openai` extra for the OpenAI-family mapping tests
  (mocked offline — no key, no network).

## Run the unit tests

```powershell
pytest tests/unit/test_structured_output.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new structured-output tests. No existing
behavior changes (default `None` path byte-identical).

## Validation scenarios (mirror the acceptance scenarios)

1. **Mapping on** — build a `ModelRequest` with `output_schema` set and drive the OpenAI
   mapping; assert the request carries `response_format` json_schema with the schema. (FR-002)
2. **Mapping off** — `output_schema=None` produces a request with **no** `response_format`
   (byte-identical to today). (FR-006)
3. **Capability probe** — `supports_structured_output(model)` returns the adapter's flag;
   a non-advertising object returns `False`. (FR-003)
4. **Web/API rejection** — POST a run with a schema to a non-supporting model → HTTP 400,
   no run started. (FR-004)
5. **Malformed schema** — POST a run with an invalid schema → HTTP 400 at request time. (FR-008)
6. **Catalog advertises** — `GET /v1/models` reports `supports_structured_output` per model.
   (FR-003)
7. **Conformance** — validate a structured response against its schema with the unit-005
   validator pack: conforming passes, non-conforming fails. (FR-005)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the public-safety scan (no private paths / secrets in the diff).

## Deferred (documented)

- Native Anthropic and Gemini structured output (their capability flag is `False` in v1, so a
  schema request to them degrades gracefully with a clear error).
