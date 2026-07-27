# Presentation State Model

080 adds no backend entity or persisted domain data. It organizes existing frontend state into explicit presentation concepts.

## App View

- chat: renders the active conversation workspace
- settings: renders the full-page capability Settings workspace

Transitions:

- chat to settings: preserve active session, entries, streaming reader, draft, attachments, selected model, scroll position, and inspection preference
- settings to chat: restore the same mounted conversation state
- unauthorized: existing AppRoot behavior returns to login

## Sidebar Presentation State

- expanded: wide-screen 240 pixel navigation
- collapsed: wide or medium 56 pixel icon rail
- drawer-open: narrow-screen overlay
- closed: narrow-screen default

Only one narrow-screen drawer may be open at a time.

## Inspection Presentation State

- closed
- inline: wide-screen panel when the remaining chat column is at least 560 CSS pixels
- overlay: medium or narrow-screen drawer above chat

The selected Skills, Tools, MCP, or Memory category remains read-only.

## Composer Attachment State

- uploading: visible with progress state and unavailable for submission
- ready: included in the next submission
- error: visible with failure state but excluded from submission
- consumed: removed immediately after successful submission construction

Consumed attachments cannot return unless the user explicitly selects them again.

## Model Presentation State

- active-session model: immutable label for an existing session
- future-session preference: user choice applied when opening the next session

The interface must not present a future preference as a live model switch.

## Async Surface State

Every Settings and inspection category uses exactly one primary state:

- loading
- ready with content
- ready empty
- error
- disabled
- policy-controlled read-only

Error and read-only are never derived from the same fallback value.
