# Implementation Plan: Document Block

**Branch**: `069-document-block` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/069-document-block/spec.md`

**Boundary**: settled by **[ADR 0011](../../docs/adr/0011-document-block-content-model.md)**.
This reverses ADR 0001's PDF deferral in a narrow way: add a minimal, additive `DocumentBlock`
content block and provider mappings that fail safely where native document input is unsupported.

## Summary

Add a first-class document content block so hosts can send PDFs/documents to document-capable model
providers as model context. The block is additive to the existing content union, preserves ordering
with existing blocks, and carries only public-safe metadata plus base64 media. Provider mappings use
native document input where supported and fail before provider submission where unsupported. The
runtime event vocabulary, `SCHEMA_VERSION`, Tool Gateway ownership, and existing non-document
content behavior remain unchanged.

## Technical Context

**Language/Version**: Python 3.11+; pydantic discriminated-union content models.

**Primary Dependencies**: none new. Reuses existing provider adapter packages and test stubs.

**Storage**: none new. Document input is represented in the content block, not durable binary
artifact storage. Binary artifact durability remains a separate follow-up.

**Testing**: pytest, offline. Focused tests for content serialization, event/checkpoint round-trip,
loop request preservation, provider mappings, unsupported-provider failure, and default
non-document behavior.

**Target Platform**: cross-platform runtime library with CLI/web/desktop host surfaces.

**Project Type**: Python runtime library with model-provider adapters and web/API host integration.

**Performance Goals**: document mapping is local and synchronous; no network call, extraction, OCR,
or file-system scan is introduced by the content model itself.

**Constraints**: additive; public-safe; no `SCHEMA_VERSION` bump; no new event type or termination
reason; no Tool Gateway change; no text extraction/OCR; unsupported providers fail safely before
submission; existing image/text/tool behavior unchanged.

**Scale/Scope**: one new content block plus provider-boundary mapping/failure behavior. Full binary
artifact durability, document search, OCR, and OpenAI Responses/Files API support are out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md`, this plan, and ADR 0011. PASS.
- **IV. Runtime Boundary Clarity**: This intentionally changes the loop-model content boundary and
  is covered by ADR 0011. Provider-specific mapping stays inside provider adapters. PASS.
- **V. Tool Gateway Ownership**: Document model input does not route through or extend the Tool
  Gateway; tools remain tool-only. PASS.
- **VI. Runtime Event Bus Ownership**: The event type remains `user-input` with an additive content
  union member; `SCHEMA_VERSION` remains unchanged and is tested. PASS.
- **VII. Public-Safe Documentation**: Document blocks and diagnostics must not expose private paths,
  credentials, raw extracted text, or local storage details. PASS.
- **VIII. No SDK Replacement**: Keeps LoopPlane's owned model boundary; no agent framework adoption.
  PASS.
- **X. Testable Evolution**: Offline tests and rollback guidance are explicit. PASS.

**Post-design re-check**: PASS. The design remains additive and scoped to the existing model/content
boundary. Complexity Tracking is not required.

## Project Structure

### Documentation (this feature)

```text
specs/069-document-block/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── document-block.md
└── checklists/
    └── requirements.md

docs/adr/0011-document-block-content-model.md
```

### Source Code (repository root)

```text
src/loopplane/model/content.py          # MODIFIED: DocumentBlock + content union
src/loopplane/model/__init__.py         # MODIFIED: public export
src/loopplane/host/__init__.py          # MODIFIED: host seam export if needed
src/loopplane/model/capabilities.py     # MODIFIED: optional document capability helper
src/loopplane/adapters/anthropic/mapping.py  # MODIFIED: native document mapping
src/loopplane/adapters/gemini/mapping.py     # MODIFIED: native document mapping when supported
src/loopplane/adapters/openai/mapping.py     # MODIFIED: fail-safe unsupported document handling
src/loopplane/webapi/multimodal.py      # MODIFIED: document upload assembly if in scope
src/loopplane/webapi/app.py             # MODIFIED: reject unsupported selected models if in scope
src/loopplane/webapi/models.py          # MODIFIED: advertise document capability if in scope
docs/api-reference.md                   # MODIFIED: public API reference if exports change
tests/contract/test_runtime_events.py   # MODIFIED: DocumentBlock event round-trip
tests/contract/test_checkpoint.py       # MODIFIED: checkpoint/rebuild round-trip if needed
tests/unit/test_document_block.py       # NEW: focused content/default behavior
tests/unit/test_anthropic_mapping.py    # MODIFIED: native document mapping
tests/unit/test_gemini_mapping.py       # MODIFIED: native document mapping
tests/unit/test_openai_mapping.py       # MODIFIED: unsupported document failure
tests/integration/test_webapi_multimodal.py  # MODIFIED if web upload assembly is included
```

**Structure Decision**: Keep the change in the existing content/model adapter boundary. The
content model defines the new block; provider adapters decide whether they can map it. Web/API
integration remains thin and only assembles/rejects document inputs at the existing model-selecting
edge.

## Complexity Tracking

> No constitution violations require justification. The content-model boundary change is ADR-backed
> and additive.
