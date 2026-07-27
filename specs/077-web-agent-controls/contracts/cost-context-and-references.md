# Contract: Cost, Context, And Safe References

## Authoritative cost reads

Reuse the existing owner-scoped/caller-scoped routes:

- `GET /v1/sessions/{session_id}/cost`
- `GET /v1/cost/monthly`

The Web client adds backend-owned response types and client methods without changing these routes.

### Display semantics

- Exact decimal zero is known zero.
- `null` remains not tracked and is never formatted as zero.
- Request failure is unavailable, not zero.
- Pricing posture from the agent-control projection distinguishes priced, partial, unpriced, and unknown.
- Session and principal-month scopes are labelled separately.
- Values refresh after a run settles, after a budget refusal, and on explicit user refresh; no new cost event/push contract is added.
- The existing local price-table estimate is removed from authoritative presentation or remains explicitly labelled as a non-authoritative estimate separate from server values.

## Budget guard posture

Budget fields from the new agent-control projection are read-only presentation metadata. Existing budget checker and pre-turn guard remain the only enforcement authority.

- `near` is a host-calculated presentation state at 80% to less than 100% of the applicable cap.
- Exact cap/rate/ledger/config values are not required in the response.
- Existing `budget-exceeded` termination remains authoritative.
- Unknown/unpriced/ledger-unavailable conditions never become `$0` or an invented remaining amount.

## Workspace context

Reuse existing capabilities/context and session-binding operations.

- The current bound context comes from existing session summary metadata.
- Available owner/allowed contexts and projected actions come from the existing capability projection.
- Bind is shown only when the context projects `bind` and the current session is owned.
- Binding never copies ownership, exposes a path, or changes the file-tool/working-directory boundary.
- Non-owner and stale authorization outcomes remain non-disclosing.

## Upload references

- Continue using the existing upload operation and its opaque `{reference, name}` response.
- Completed references are retained only in the current draft/session UI state.
- Explicit send passes them through the existing structured `uploads` request field.
- Frontend code does not concatenate references into the user's prompt.
- A non-image upload is eligible only after explicit send, existing principal ownership validation, and an authoritative `attach_non_image_upload` action in the latest control projection. Image uploads keep the existing image-block behavior.
- The backend may assemble at most 8 compact UTF-8 JSON metadata blocks per run, each at most 256 bytes and containing exactly `{"type":"loopplane_upload_reference","reference":"<server-generated opaque reference>","reader":"read_upload"}`. Filename, MIME string, path, content, and arbitrary user metadata are absent.
- WebAPI only assembles already validated metadata. It never resolves, authorizes, or invokes `read_upload`; later reads remain exclusively inside the existing Tool Gateway.
- `attach_non_image_upload` is projected only when the host's existing Gateway description advertises `read_upload`. If availability changes, or a stale/direct client submits an ineligible non-image reference, the request fails publicly and safely before model execution without echoing the reference.
- Agent controls do not add upload list/get/download/delete/retention contracts.
- Raw upload bytes/content and host paths are never fetched by the controls surface.

## Artifact references

- Preserve `artifact_reference` from normalized tool-completed input in the transport-neutral chat/tool state.
- Show safe current-session reference metadata only: opaque reference, bounded label/kind/status, and safe actions.
- Agent controls do not call the existing raw-content artifact retrieval route.
- An allowed action may attach the opaque reference to editable composer text/metadata for a later explicit send; any agent read continues through an existing authorized handoff/Gateway path.
- No artifact index, cross-session discovery, content browser, durable browser cache, sharing, or new persistence boundary is added.

## Public safety

The controls and errors exclude:

- raw upload/artifact content;
- absolute/private paths;
- provider/MCP credentials or metadata;
- another principal's identifiers or existence;
- raw exceptions and rejected inputs.
