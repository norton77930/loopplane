# Quickstart: Multimodal Input

## Prerequisites

- Dev install (`pip install -e ".[dev]"`), Python 3.12+. The offline tests need no
  API key and no network.
- To actually send an image to a real model: a vision-capable provider (e.g.
  Anthropic / OpenAI / an OpenRouter vision model) configured as a host, plus its
  injected credential (never committed — Constitution VII).

## Automated validation (primary, offline)

```powershell
uv run pytest tests/unit/test_capabilities.py tests/unit/test_multimodal_assembly.py tests/integration/test_webapi_multimodal.py tests/contract/test_runtime_events.py tests/contract/test_api_reference.py -q
```

**Expected**: green — `accepts_media(model)` reads the duck-typed method (else
`False`); the assembly helper embeds image uploads as leading `ImageBlock`s
(non-images skipped), enforces ownership + the size cap, and degrades on a
text-only model; a run carrying an image makes the scripted model receive an
`ImageBlock`; the `/v1/models` catalog reports `accepts_media`; the event serde
round-trip is lossless for an `ImageBlock`-bearing `UserInputEvent`; and the
api-reference bijection includes the new `accepts_media` name.

Then the full gates:

```powershell
uv run ruff check .; uv run ruff format --check .; uv run mypy; uv run pytest -q
```

## Sending an image to the model (illustrative)

1. Upload the image (028, unchanged), getting a reference:

   ```text
   POST /v1/uploads?name=diagram.png   (body: the raw image bytes)
   -> { "reference": "<ref>", "name": "diagram.png" }
   ```

2. Send a run/turn that carries the upload — the image reaches the model as a
   leading `ImageBlock`, the prompt follows:

   ```text
   POST /v1/runs/events
   { "prompt": "What is in this diagram?", "uploads": [ { "reference": "<ref>" } ] }
   ```

3. The catalog advertises which models accept images, so a client can hide the
   attach affordance for text-only models:

   ```text
   GET /v1/models
   -> [ { "id": "claude", "label": "Claude", "accepts_media": true },
        { "id": "local",  "label": "Local Llama", "accepts_media": false } ]
   ```

   Sending an image to a model whose `accepts_media` is `false` returns a clear
   normalized error (HTTP 400) and dispatches no image.

## Embedding a model directly (non-web)

```python
from loopplane.model import accepts_media
from loopplane.model.content import ImageBlock, TextBlock

if accepts_media(model):
    blocks = [ImageBlock(media=b64, format="image/png"), TextBlock(text="describe this")]
    await host.run(blocks, on_event)
else:
    ...  # text-only model: degrade (omit the image / read it as text via read_upload)
```

## Rollback

Additive. Remove `RunRequest.uploads` + `loopplane.webapi.multimodal` + the
`image_media_type` helper + the `accepts_media` flags
(`loopplane.model.capabilities`, the two adapter configs, the 035 constructor
params) and the api-reference additions; units 020/028/035, the content model, the
event schema, the runtime core, the Tool Gateway, and the artifact store are
untouched (Constitution X). Image **input** simply stops being assembled at the
web edge; non-image `read_upload` access (028) is unaffected.
