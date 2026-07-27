# Contract: Managed MCP Endpoint and Lifecycle Remediation

## Endpoint admission

Browser-managed MCP writes retain the existing request and response envelopes. The domain result is `invalid` and public-safe when:

- transport is stdio or unsupported;
- the endpoint is empty or has no host;
- scheme is incompatible with transport;
- userinfo, query, or fragment is present;
- URL or port parsing fails;
- the host endpoint policy is absent, raises, or denies the endpoint.

No rejected endpoint, command, argument, credential-like value, private path, or raw exception may appear in durable state or public responses.

## Persistence boundary

Every MCP record written to capability settings must pass the same structural endpoint validation. Persistence does not apply principal-aware endpoint policy. Legacy invalid records may be loaded for safe listing/update/deletion but may not connect or activate.

## Host API

The maintainer approved these public Python host mutations becoming asynchronous in 081:

- managed-MCP upsert/update
- managed-MCP delete

Callers must await completion. Existing HTTP routes remain asynchronous and retain their paths, request bodies, response bodies, and status/result values.

## Runtime lifecycle

- Successful update persists `disconnected`, then removes the old owner-scoped adapter.
- Successful delete removes durable state, then removes the old owner-scoped adapter.
- Structural invalidity, endpoint-policy denial, connection failure, candidate failure, state-update failure, and registry-replacement failure all remove the old owner-scoped adapter before returning a terminal result.
- Successful reconnect replaces the adapter through the existing Gateway scoped-adapter operation.
- Removal makes tools immediately unavailable to new resolution.
- Already-leased invocations may complete.
- The retired adapter shuts down exactly once after the final lease is released.
- A principal's lifecycle operation does not alter another principal's registry.

## Unchanged boundaries

- No Gateway SPI or stage-order change.
- No direct host tool resolution, invocation, or shutdown.
- No Event Bus or checkpoint change.
- No new status enum or HTTP route.
- No new dependency or default change.
