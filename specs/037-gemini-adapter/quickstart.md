# Quickstart: Native Google Gemini Adapter

## Prerequisites

- Dev install (`pip install -e ".[dev]"`), Python 3.12+. The offline tests need
  **no API key and no network** (an injected stub client bypasses the SDK).
- To actually call Gemini: `pip install ".[gemini]"` (the official `google-genai`
  SDK) plus a Google API key, supplied via the environment — **never committed**
  (Constitution VII).

## Automated validation (primary, offline)

```powershell
uv run pytest tests/unit/test_gemini_mapping.py tests/contract/test_api_reference.py -q
```

**Expected**: green — the request mapping (`build_contents`/`build_tools`) and the
`GeminiStreamDecoder` are asserted against Gemini-shaped stand-in chunks, and the
api-reference bijection includes the new `loopplane.adapters.gemini` package. The
shared overflow/failure suites also exercise `"gemini"` via the parametrized
provider stub:

```powershell
uv run pytest tests/integration/test_us2_model_overflow.py tests/integration/test_us3_model_failures.py tests/unit/test_capabilities.py -q
```

Then the full gates:

```powershell
uv run ruff check .; uv run ruff format --check .; uv run mypy; uv run pytest -q
```

## Using the adapter (illustrative)

```python
import os

from loopplane.adapters.gemini import GeminiConfig, GeminiModel
from loopplane.host import LoopPlaneHost, RuntimeConfig

# The key is injected from the environment, never committed (Constitution VII):
model = GeminiModel(GeminiConfig(model="gemini-2.5-flash", api_key=os.environ["GEMINI_API_KEY"]))

host = LoopPlaneHost(RuntimeConfig(model=model))
# host.run(...) streams text/tool/usage exactly as for the other adapters.
```

Register it as a model host in the `/v1/models` registry exactly as the OpenAI host
is registered (unit 028); the existing UI model selector lists it with no frontend
change. Gemini is vision-capable, so the host advertises `accepts_media=True` and
an `ImageBlock` reaches the model as an `inline_data` part (unit 036).

## Opt-in live check (excluded from the gates)

```powershell
$env:GEMINI_API_KEY="..."; $env:LOOPPLANE_GEMINI_MODEL="gemini-2.5-flash"; uv run pytest tests/live -q
```

Without both env vars the live Gemini test is skipped (see
`docs/real-model-validation.md`).

## `thought_signature` note

Multi-turn tool use works against Gemini 3 because the adapter attaches Google's
official `"skip_thought_signature_validator"` sentinel when re-mapping a prior tool
call — so **no content-model change** is needed. Preserving the *real* per-call
signature (for best cross-turn reasoning continuity) is a documented deferred
follow-up (it would need a content-model field — a Constitution VI / ADR matter).

## Rollback

Additive. Remove `src/loopplane/adapters/gemini/`, the `test_gemini_mapping.py`
module, the Gemini entries in `tests/integration/provider_stubs.py` /
`tests/unit/test_capabilities.py` / `tests/live/test_live_models.py`, the `gemini`
extra in `pyproject.toml`, and the `### loopplane.adapters.gemini` api-reference
section; units 020/035/036, the content model, and the event schema are untouched
(Constitution X).
