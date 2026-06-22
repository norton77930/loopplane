# Quickstart: Document Block Validation

## Prerequisites

- Python environment managed by `uv`
- Existing LoopPlane test dependencies installed

## Focused Validation

Run the focused document-block tests after implementation:

```powershell
uv run pytest -q tests/unit/test_document_block.py
```

Expected outcomes:

- `DocumentBlock` validates non-empty media and media type.
- `DocumentBlock` round-trips through content serialization.
- Existing text/image/tool content still round-trips unchanged.
- A model request containing text plus document preserves block order.

## Provider Mapping Validation

Run provider adapter mapping tests:

```powershell
uv run pytest -q tests/unit/test_anthropic_mapping.py tests/unit/test_gemini_mapping.py tests/unit/test_openai_mapping.py
```

Expected outcomes:

- Anthropic mapping emits a native document input block.
- Gemini mapping emits native inline data for document input.
- OpenAI chat-compatible mapping fails safely before provider submission for document input.
- No failure message contains raw document bytes, private paths, credentials, or extracted text.

## Event And Checkpoint Validation

Run the existing event/checkpoint contract tests plus focused additions:

```powershell
uv run pytest -q tests/contract/test_runtime_events.py tests/contract/test_checkpoint.py
```

Expected outcomes:

- `SCHEMA_VERSION` remains unchanged.
- `user-input` events preserve document-bearing content.
- Checkpoint rebuild preserves document-bearing user history.

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
