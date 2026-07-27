# Contract: Capability Settings UI

## Purpose

Define the browser behavior for the independent capability settings view.

## Entry And Navigation

- A settings entry is available from the app shell/header.
- Settings replace the central message workspace while open; the session sidebar, header, composer, and chat state remain mounted.
- Opening settings does not remove the chat composer, session list, or read-only inspection capability.
- The existing inspection panel remains metadata-only and read-only.
- The settings view can be closed or navigated away from without losing existing chat/session state.

## Shared View Rules

- Each capability section shows loading, empty, success, disabled, and public-safe error states.
- Owned resources show the actions available to the current principal.
- Shared host resources are marked read-only and do not show mutation actions.
- Mutating actions refresh the affected list/detail state after completion.
- Delete actions require explicit confirmation.
- No provider credential, API key, secret, token, or MCP authentication token field is rendered.

## Memory And Skills

- Memory section supports list, open detail, create, update, and delete for owned memory.
- Skills section supports list, open detail, create/update, import, and delete for owned skills.
- Invalid skill imports show public-safe validation state.
- Shared host skills and memory show read-only status.

## MCP And Workspace Context

- MCP section supports list, open detail, add/update, reconnect, and delete for owned configurations.
- MCP creation offers HTTP, SSE, and WebSocket only and never renders stdio command or argument controls.
- MCP status includes connected, disconnected, failed, and unavailable states with public-safe problem text.
- Workspace context section supports list, open detail, create/update, delete, and bind to an owned session.
- The active session context is visible before the user sends a turn.

## Schedules And Model Defaults

- Schedule section supports list, open detail, create/update, enable, disable, run now, and delete.
- Schedule create/update requires an instruction even though the additive wire field remains optional for older clients.
- Disabled schedule run-now attempts show a public-safe refusal.
- Model default section renders a select control populated from the host model catalog.
- Invalid or unavailable model defaults fall back safely and remain visible as fallback/unavailable.

## Mutation Gate

- When mutation is disabled, the settings view keeps read-only lists available and hides or disables mutation controls.
- Attempts to mutate through stale UI state show a public-safe disabled result.

## Accessibility And Testability

- Interactive controls have stable accessible names.
- Status changes are visible in text for automated and manual verification.
- Error states avoid exposing raw internal details.
