# Phase 1 Data Model: Web Agent Model Selection & File Attachments

Additive web-layer types. No runtime type change; the content model is unchanged.

## Model catalog (web/API layer)

```python
@dataclass(frozen=True)
class ModelHost:
    label: str
    host: LoopPlaneHost          # a pre-built single-model host (shares the checkpoint root)

# create_app(host, *, models: Mapping[str, ModelHost] | None = None, uploads: UploadStore | None = None, ...)
```

`GET /v1/models` → `list[ModelInfo]`:

```python
class ModelInfo(BaseModel):       # metadata-only — never an api key
    id: str
    label: str
```

Run routing: `RunRequest` gains `model: str | None = None`. The endpoint selects
`models[model].host` when `model` is a known id, else the default `host`; an **unknown** id → `400`
(clear error). The chosen host runs/resumes the session from the **shared checkpoint** — one model
per run.

## UploadStore (per-reference blob store)

```python
@dataclass(frozen=True)
class StoredUpload:
    reference: str               # unguessable token (the capability)
    name: str                    # original filename (sanitized, public-safe)
    owner: str                   # principal id (recorded; never returned in the read)
    size: int

class UploadStore:
    def __init__(self, root: Path, *, max_bytes: int = ...) -> None: ...
    def save(self, owner: str, name: str, data: bytes) -> StoredUpload: ...   # raises on over-limit
    def read(self, reference: str) -> bytes | None: ...                        # by capability; None if absent
    def info(self, reference: str) -> StoredUpload | None: ...
```

`POST /v1/uploads` (auth-gated, multipart) → `UploadResult { reference, name }`. The owner is the
caller's principal; the reference is returned only to that caller.

```python
class UploadResult(BaseModel):
    reference: str
    name: str
```

## read_upload tool (inside the Tool Gateway)

```python
# make_read_upload_tool(store: UploadStore) -> ToolSpec
ToolDescriptor(
    name="read_upload",
    description="Read the text content of an uploaded file by its reference.",
    input_schema={ "type": "object", "properties": { "reference": {"type": "string"} },
                   "required": ["reference"], "additionalProperties": False },
    read_only=True,
    source="internal",
)
# handler(call_input, RunContext) -> [TextBlock(text=<file text>)]  (or a clear "not found" block)
```

The handler reads `store.read(call_input["reference"])` and returns the decoded text (bounded);
a missing/oversized reference → a public-safe "not found"/"too large" `TextBlock`, never an
exception. The tool **reads only** — it never writes, embeds, or persists (transient input by id).

## Frontend types (`apps/web/src/api/types.ts`)

```ts
export interface ModelInfo { id: string; label: string; }
export interface UploadResult { reference: string; name: string; }
```

Client: `listModels(): Promise<ModelInfo[]>`; `uploadFile(file): Promise<UploadResult>` (with
progress); the run/open carry the selected `model` id; the composer appends each `reference` to the
prompt so the agent can `read_upload` it.

## State (composer)

| Field | Meaning |
|---|---|
| `selectedModel: string \| null` | the session's chosen model id (null = default host) |
| `attachments: { name, reference, status }[]` | uploaded files (status: uploading / done / error) |

On send: route the run with `selectedModel`; append the done attachments' references to the prompt;
block send while any attachment is still uploading or errored (FR-005).
