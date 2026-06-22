# Quickstart: Gemini Signature Validation

## Prerequisites

- Python environment managed by `uv`
- Existing LoopPlane test dependencies installed

## Focused Gemini Validation

Run the Gemini mapping tests after implementation:

```powershell
uv run pytest -q tests/unit/test_gemini_mapping.py
```

Expected outcomes:

- Gemini decoder preserves a provider signature on the matching tool call.
- Gemini decoder treats missing, empty, or non-string signatures as absent.
- Gemini request mapping replays a preserved signature outside tool arguments.
- Gemini request mapping keeps the existing fallback for unsigned tool calls.
- Multiple tool calls preserve their signatures independently and in order.

## Event, Checkpoint, And Gateway Validation

Run contract tests covering replayable content and gateway separation:

```powershell
uv run pytest -q tests/contract/test_runtime_events.py tests/contract/test_checkpoint.py tests/integration/test_us1_tool_run.py
```

Expected outcomes:

- `SCHEMA_VERSION` remains unchanged.
- Signature-bearing tool-call content round-trips through events and checkpoints.
- Gateway-facing tool input does not contain provider metadata.

## Non-Gemini Regression Validation

Run existing non-Gemini mapping and model-boundary tests:

```powershell
uv run pytest -q tests/unit/test_openai_mapping.py tests/unit/test_anthropic_mapping.py tests/contract/test_model_boundary.py
```

Expected outcomes:

- OpenAI and Anthropic mappings remain unchanged for unsigned tool calls.
- Generic model-boundary behavior remains unchanged.

## Full Gate

Before final review:

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

The final board validation also requires `git diff --check`, `openspec/` scan, and public-safety
scan.
