# Shared UI Compatibility Contract

## Scope

This contract protects Web behavior and the source-level interface consumed by apps/desktop while 080 changes presentation.

## Stable shared exports

The following named exports and import paths remain valid:

- components/MessageList exports MessageList
- components/ApprovalDialog exports ApprovalDialog
- components/QuestionDialog exports QuestionDialog
- state/chat exports initialState, reduce, userPrompt, and errored
- api/types exports RawEvent and the currently consumed public types

## Stable component behavior

### MessageList

- Consumes the existing entries collection and optional action callbacks.
- Preserves message order and existing user, assistant, reasoning, tool, termination, and empty-state semantics.
- Loading presentation may change, but loading must not replace already rendered entries.

### ApprovalDialog

- Preserves toolName and onDecide inputs and all existing decision values.
- Remains keyboard reachable and returns one decision per user action.

### QuestionDialog

- Preserves prompt, options, onAnswer, and onClose inputs.
- Remains usable with either listed options or free text.

## Browser-only boundaries

Shared modules imported by Desktop must not read browser storage, fetch, EventSource, WebSocket, or browser-only bridge objects during module initialization. Browser behavior stays in AppRoot, App, existing transports, hooks, or explicit event handlers.

## App shell contract

AppShell remains presentation-only and receives React nodes for Sidebar, Header, banner, content, Composer, and optional panel. It must not own API, transport, session, or runtime-event behavior.

## Settings contract

CapabilitySettingsView remains the production entry for existing capability APIs. Category components remain private implementation details and do not change request or response shapes.

## CSS state contract

Interactive state is exposed through semantic classes, aria attributes, or data attributes. Styling must not depend on DOM order where an explicit state attribute is available.
