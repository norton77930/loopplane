# Quickstart: Web Agent Model Selection & File Attachments

Validates the additive model catalog/routing + the upload endpoint/tool and proves both gates stay
green. No constitution ADR.

## Prerequisites

- The Python `web` extra installed; the `apps/web` toolchain installed. **No new dependency.**
- For real models: configure the catalog with unit-020 adapter hosts (each behind its extra). The
  automated tests use `ScriptedModel` hosts + a stubbed fetch.

## Automated gates (authoritative)

```bash
# Backend
pytest tests/unit/test_uploads.py tests/integration/test_webapi_model_files.py
pytest                # full suite stays green (additive — SC-004)

# Frontend
cd apps/web
npm run typecheck && npm test && npm run build
```

## Manual QA (against a live host with >1 model + uploads configured)

1. **Model catalog + select** — open the composer model selector; the configured models are listed
   with the current selection indicated (FR-001/002, SC-001).
2. **Routed run** — pick a model and send; the run is served by that model's host (one model per
   run); change the model and send again — the next turn uses the new model, resuming from the
   shared checkpoint (FR-003/004).
3. **Attach** — attach one or more files (picker/drag-drop); each uploads with progress; an
   over-limit/invalid file is rejected with a clear error and the message is not sent missing an
   attachment (FR-005/006/009, SC-002).
4. **Agent reads** — during the run, the agent calls the `read_upload` tool to read an attachment's
   content on demand; the file is **not** embedded in the prompt and is **not** stored as an artifact
   or memory (FR-007).
5. **Auth** — model selection + uploads honor the auth boundary; an attachment is scoped to its
   owner (FR-008).

## Expected outcome

A user selects a model (one per run, web-layer routed) and attaches files the agent reads via the
gateway tool (SC-001/002); the change is **additive** — runtime core, one-model-per-run, content
model, Tool Gateway, Event Bus, and existing endpoints unchanged, Python suite green (SC-003/004);
the `apps/web` gate is green (SC-005); a public-safety scan is clean (SC-006).

## Rollback

Drop the catalog/routing + the upload endpoint/`UploadStore`/`read_upload` tool + the composer model
selector/attachments. The prior single-model, text-only app returns; the runtime is unaffected
(Constitution X).
