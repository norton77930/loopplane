# Contract: Allowed Contexts and Shared Capability Details

## Allowed context provider

The host may configure one callable provider that receives the requesting principal ID and returns contexts explicitly allowed to that principal. The provider is absent by default.

The manager rebuilds every allowed context as a safe projection. Provider-supplied ownership, scope, actions, status, and problem values are not trusted.

## Visibility and collisions

- Lists include owned contexts plus valid allowed projections for that principal.
- Duplicate provider IDs are excluded.
- Owner/provider ID collisions are excluded from list, detail, and bind.
- Provider errors or invalid values fail closed for allowed contexts while owned contexts remain available.
- Unknown, unauthorized, collided, and cross-principal context operations use the same non-disclosing not-found behavior.

## Binding

- Only a session owned by the requester may be bound.
- Owned contexts retain their existing bind behavior.
- Allowed contexts expose Bind only when projected actions include it.
- Binding stores session metadata only; it does not copy or mutate the allowed context.
- With no provider configured, owner-only behavior is unchanged.

## Shared details

All settings interactions are driven by projected actions, not scope labels alone.

- Shared memory Open shows only the documented memory projection fields; its snippet is the first at most 160 Unicode code points, its shape-preserving `content` value is empty, and no editable full content or nested metadata is exposed.
- Shared skill Open shows only the documented metadata/source/status fields; its shape-preserving `instructions` value is empty and is not displayed.
- Shared MCP Open shows only transport/status/safe tool names and count plus common safe projection fields; no URL, authentication material, owner identity, private path, nested provider metadata, or raw error is exposed.
- Allowed context Open shows only the documented safe context fields; Bind may be present; Update/Delete and nested provider metadata are absent.
- A resource without `open` does not expose a detail action.
- Shared detail never reuses an editable owner form.

## Presentation requirements

The detail experience follows the existing Settings accessibility and responsive behavior: keyboard reachability, Escape dismissal where modal, focus return, localized labels, reduced-motion and forced-color compatibility, and no horizontal overflow at required reflow widths.

## Unchanged contracts

Existing capability list/detail/bind routes and generated response shapes remain unchanged. Owner detail remains complete. Shared owner-only string fields use safe empty values and are not displayed.
