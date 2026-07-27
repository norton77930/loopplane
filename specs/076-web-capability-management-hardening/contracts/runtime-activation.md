# Contract: Runtime Activation

## Purpose

Define how user-owned capabilities managed through settings become available to the owner's later runtime sessions while preserving Tool Gateway ownership, Runtime Event Bus ownership, and principal scoping.

## Activation Rules

- Capability changes apply to later eligible turns or sessions.
- Owner runtime activation is default-off and can be disabled independently from settings reads.
- An already-running model turn remains stable and is not mutated mid-flight.
- Runtime activation is scoped to the active `principal_id`.
- Non-owner capabilities are absent from prompts, tool descriptors, tool execution, and session-visible metadata.
- Shared host capabilities remain available according to existing host policy and are not user-mutable.

## Memory Activation

- Owned memory entries are eligible for owner-only prompt augmentation.
- Shared host memory remains eligible only when already public-safe and allowed by host policy.
- Prompt augmentation must not include another principal's owned memory.

Acceptance checks:

- Owner's later session can receive the owned memory augmentation.
- Non-owner session receives no owner-private memory content.

## Skill Activation

- Valid owned skills are advertised and exposed as owner-only managed tools.
- Invalid owned skills are listed in settings with a public-safe problem and are not advertised or executable.
- Shared host skills remain registered as shared read-only capability metadata where applicable.

Acceptance checks:

- Owner's later session sees and can invoke the owned skill through normal gateway execution.
- Non-owner session does not see the descriptor and cannot execute the owned skill by guessed name.

## MCP Activation

- Successful reconnect refreshes the managed MCP adapter and owner-visible tool descriptors.
- Failed reconnect records a public-safe status without registering failed tools.
- Replacing a managed MCP adapter must shut down the previous managed adapter for that owner/configuration.
- Replacement leases the previous adapter until in-flight calls complete, then shuts it down exactly once.
- Browser-managed stdio never enters the managed adapter registry; approved network MCP uses an atomically connected candidate.
- Tool calls from managed MCP configurations execute only through the Tool Gateway.

Acceptance checks:

- Owner's later session sees refreshed MCP descriptors after reconnect.
- Non-owner session cannot see or execute owner-managed MCP tools.
- Failed MCP calls return normalized public-safe gateway errors.

## Gateway Boundary Rules

- Existing shared tool registration remains unchanged.
- Scoped managed adapters are registered, described, replaced, and shut down inside the Tool Gateway boundary.
- Descriptor listing must support principal-aware filtering.
- Concurrency metadata lookup and execution resolution must use the same principal-aware registry view.
- Execution must fail closed if a scoped tool is called outside its allowed principal scope.
- No component outside the Tool Gateway may resolve or execute managed tools directly.

## Event Rules

- No new runtime event types are introduced.
- Existing normalized tool-call started/completed events continue to represent managed tool execution.
- UI-specific formatting remains outside the Agent Loop.
