# Implementation Plan: Multimodal Input (Image Attachments)

**Branch**: `036-multimodal-input` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/036-multimodal-input/spec.md`

**ADR**: [docs/adr/0001-multimodal-content.md](../../docs/adr/0001-multimodal-content.md) — the repository's first ADR; settles PDF, binary durability, capability negotiation, and size caps.

## Summary

Deliver **image input end-to-end** by wiring the existing upload path (028) into
the existing `ImageBlock` content model at the **web edge**, plus **provider
capability negotiation** so a text-only model degrades with a clear normalized
error. Per the ADR, the content model and the event schema are **unchanged**
(`ImageBlock` is already in `ContentBlock`/`OutputBlock` and already round-trips
through the event schema and both provider mappings); **PDF is deferred** (no
base64 PDF in OpenAI chat-completions; would pull in binary artifact durability +
a non-text gateway handoff). The change is additive in `loopplane.model` (a
duck-typed `accepts_media` helper), the two real adapters + the 035 constructors
(an `accepts_media` flag), and `loopplane.webapi` (an optional `RunRequest.uploads`
field, an image-assembly helper, a catalog capability flag, and a degradation
check on the run endpoints). Native Gemini stays a deferred 035 follow-up.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new. Image bytes are base64-encoded with the
standard library; the web layer rides the existing optional `web` extra (FastAPI).

**Storage**: reuses the 028 per-principal `UploadStore` (no change).

**Testing**: pytest (offline, deterministic) — a scripted model that records the
`ModelRequest` it received (to assert a leading `ImageBlock`); an in-process
FastAPI `TestClient` (no socket/network) for the web edge; the existing event
serde round-trip extended to an `ImageBlock`-bearing `UserInputEvent`. Any live
multimodal model check is opt-in/secret-gated (none added here).

**Target Platform**: cross-platform library + web/API host.

**Project Type**: single project — embeddable Python library/runtime + its
web/API transport.

**Constraints**: no change to the content model, the event schema/`SCHEMA_VERSION`,
the Agent Loop, the runtime controller, the Tool Gateway execution path, or the
artifact store; the `ModelBoundary` Protocol stays two methods; credentials never
committed.

**Scale/Scope**: one new helper in `loopplane.model` (+ its `__all__`/doc); an
`accepts_media` flag on two configs + two 035 constructors; a small image-assembly
helper + an optional request field + a catalog flag + a degradation check in
`loopplane.webapi` (one new public request/helper name → api-reference); new
offline tests; tracking-doc updates.

## Constitution Check

*GATE: pass before Phase 0; re-check after design.*

- **I — Spec-First**: PASS (traces to spec 036 + ADR 0001).
- **II — Greenfield**: PASS (fresh code; no legacy copied).
- **III — Harness before automation**: PASS (no loop-automation surface touched).
- **IV — Runtime Boundary Clarity**: PASS **with ADR**. A content-model change
  *would* need an ADR (IV); the ADR's decision is that **no content-model change
  is made** — image input reuses the existing `ImageBlock`. Capability negotiation
  is additive (a duck-typed helper) and is enforced at the web/API
  model-selecting boundary (028 owns selection), not in the loop. ADR 0001 records
  the boundary analysis.
- **V — Tool Gateway Ownership**: PASS (the gateway is untouched; non-image
  uploads still flow through the existing `read_upload` gateway tool; no new
  gateway stage).
- **VI — Event Bus / schema contract**: PASS. No event added; `SCHEMA_VERSION`
  unchanged. The `ImageBlock` already in `UserInputEvent.blocks` now reaches the
  model on the input path; the serde round-trip test is **extended** to assert an
  `ImageBlock`-bearing `UserInputEvent` is lossless (a content-block change in the
  schema MUST be tested — here we prove the existing block is contract-safe).
- **VII — Public-Safe**: PASS (no key/secret/private path; normalized errors carry
  no provider internals; api-reference bijection kept green).
- **VIII — No SDK Replacement**: PASS (no framework adopted; runtime core
  unchanged).
- **IX — Reference, not clone**: PASS (image wire formats reuse the 020 mappings;
  OpenRouter/Ollama inherit via 035).
- **X — Testable Evolution**: PASS (offline tests for both stories + the round-trip
  extension; rollback = remove the request field/helper/flags). PDF/binary
  durability decomposed out as a documented follow-up rather than a big-bang
  change.

No violations → Complexity Tracking empty. (The ADR is the IV/VI artifact that
authorizes the boundary review; its conclusion is a *no-op* on the content model.)

## Project Structure

### Documentation (this feature)

```text
specs/036-multimodal-input/
├── plan.md, research.md, data-model.md, quickstart.md, spec.md, tasks.md
├── contracts/multimodal.md
└── checklists/requirements.md

docs/adr/0001-multimodal-content.md   # the narrowed ADR (first in repo)
```

### Source Code (repository root)

```text
src/loopplane/model/
├── content.py            # UNCHANGED (ImageBlock already present) — ADR D1
├── boundary.py           # UNCHANGED (ModelBoundary stays 2 methods) — ADR D5
├── capabilities.py       # NEW: accepts_media(model) -> bool (duck-typed helper)
└── __init__.py           # MODIFY: export accepts_media (+ __all__)

src/loopplane/adapters/
├── anthropic/config.py   # MODIFY: + accepts_media: bool = True
├── anthropic/adapter.py  # MODIFY: + accepts_media() method
├── openai/config.py      # MODIFY: + accepts_media: bool = True
├── openai/adapter.py     # MODIFY: + accepts_media() method
└── openai_compat/__init__.py  # MODIFY: openrouter_model(accepts_media=True) / ollama_model(accepts_media=False)

src/loopplane/webapi/
├── models.py             # MODIFY: RunRequest + uploads; ModelInfo + accepts_media
├── uploads.py            # MODIFY: + image media-type detection helper (pure)
├── multimodal.py         # NEW: assemble_blocks(prompt, uploads, store, *, max_image_bytes) -> list[ContentBlock]
├── app.py                # MODIFY: ModelHost + accepts_media; run endpoints build blocks + degrade
└── __init__.py           # MODIFY: export the new request/assembly name (+ __all__)

docs/api-reference.md     # MODIFY: + accepts_media (model); webapi additions (014 bijection)

tests/unit/test_capabilities.py        # NEW: accepts_media helper + adapter flags
tests/unit/test_multimodal_assembly.py # NEW: image assembly (images only, order, cap, non-image skip)
tests/integration/test_webapi_multimodal.py # NEW: image reaches the model; text-only degrades; catalog flag
tests/contract/test_runtime_events.py  # MODIFY: round-trip an ImageBlock-bearing UserInputEvent (VI)
```

**Structure Decision**: A new `loopplane.webapi.multimodal` module keeps the
image-assembly logic cohesive and pure (testable without a server); the
capability probe lives in a new `loopplane.model.capabilities` so the runtime
exposes it to *any* embedder (not just the web host) without touching the
`ModelBoundary` Protocol. The content model and event schema are deliberately
**not** in the change set (ADR D1/D2).

## Complexity Tracking

> No Constitution Check violations. The ADR (IV/VI) authorizes the boundary
> review and concludes with **no content-model / event-schema change**.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
