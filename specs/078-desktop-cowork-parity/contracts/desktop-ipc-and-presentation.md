# Contract: Desktop IPC and Shared Presentation Boundary

**Status**: Proposed — implementation requires the 078 human gate.

## 1. Trust boundary

```text
Renderer (untrusted presentation)
  -> typed, frozen preload facade
Preload (isolated adapter)
  -> operation-specific Electron IPC
Electron main (trusted Desktop owner)
  -> private Desktop stdio RPC V1
Python sidecar (trusted local adapter)
  -> LoopPlaneHost public facades
Runtime controller / Gateway / Event Bus
```

Rules:

- Renderer never receives Node.js, Electron, child-process, raw filesystem, raw IPC, raw RPC, principal, absolute path, provider secret, private rule/configuration, PID, stderr, or raw exception access.
- Electron main is the only sidecar process owner and stdio reader/writer.
- The sidecar is the only Desktop process that integrates with runtime, and it does so through `LoopPlaneHost` public facades only.
- Existing runtime enforcement remains in Host/controller/Gateway. UI state is never authorization state.

## 2. BrowserWindow security requirements

Every production and validation window uses:

- `contextIsolation: true`;
- `sandbox: true`;
- `nodeIntegration: false`;
- no remote module;
- no navigation to arbitrary origins;
- no untrusted embedded web content in the privileged renderer;
- a restrictive HTML-delivered Content Security Policy for bundled local assets, with at least `default-src 'self'`, `script-src 'self'`, `connect-src 'none'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`, and `form-action 'none'`; any additional `style-src`, `img-src`, or `font-src` allowance MUST be limited to assets the bundled renderer actually needs and MUST NOT enable remote origins;
- top-frame `will-navigate` denial for every target other than the exact already-loaded bundled application entry;
- `setWindowOpenHandler` denial for every `window.open` request in V1, with no privileged child window or renderer-controlled external-open fallback;
- deny-by-default permission request and permission check handlers for the renderer session; 078 requests no camera, microphone, geolocation, notifications, MIDI, clipboard-read, or other browser permission;
- a preload path resolved from packaged application resources, not a development checkout.

Development-server allowances, if retained for local development, are isolated behind development-only composition and never weaken packaged-window settings.

## 3. Preload facade

Preload exposes one frozen object, planned as `window.loopplaneDesktop`. It contains operation-specific methods grouped by domain. Exact TypeScript names may be normalized during implementation, but the following semantic allowlist is binding:

```typescript
interface LoopPlaneDesktop {
  app: {
    status(): Promise<DesktopStatus>;
    shutdown(): Promise<void>;
    subscribeStatus(handler: (event: DesktopStatusEvent) => void): () => void;
  };
  sessions: {
    list(query?: SessionQuery): Promise<SessionPage>;
    history(sessionId: SessionId, cursor?: string): Promise<HistoryPage>;
    rename(sessionId: SessionId, title: string): Promise<SessionSummary>;
    setStarred(sessionId: SessionId, starred: boolean): Promise<SessionSummary>;
    delete(sessionId: SessionId, confirmation: Confirmation): Promise<void>;
    fork(sessionId: SessionId, source: ForkPoint, confirmation: Confirmation): Promise<SessionSummary>;
    createInteractive(input: CreateInteractionInput): Promise<InteractionHandle>;
    resumeInteractive(input: ResumeInteractionInput): Promise<InteractionHandle>;
    releaseInteractive(subscriptionId: SubscriptionId): Promise<void>;
  };
  projects: {
    list(): Promise<DesktopProject[]>;
    create(input: ProjectCreateInput): Promise<DesktopProject>;
    rename(projectId: ProjectId, label: string): Promise<DesktopProject>;
    remove(projectId: ProjectId, confirmation: Confirmation): Promise<void>;
    assignSession(projectId: ProjectId | null, sessionId: SessionId): Promise<void>;
  };
  interaction: {
    submit(subscriptionId: SubscriptionId, input: SubmitInput): Promise<AcceptedRun>;
    cancel(subscriptionId: SubscriptionId): Promise<void>;
    answerApproval(subscriptionId: SubscriptionId, requestId: string, decision: ApprovalDecision): Promise<void>;
    answerQuestion(subscriptionId: SubscriptionId, requestId: string, answer: QuestionAnswer): Promise<void>;
    subscribe(subscriptionId: SubscriptionId, handler: (event: DesktopInteractionEvent) => void): () => void;
  };
  inspection: {
    get(sessionId: SessionId): Promise<InspectionProjection>;
    audit(sessionId: SessionId, cursor?: string): Promise<TurnAuditPage>;
    agentControls(sessionId: SessionId): Promise<AgentControlsProjection>;
  };
  capabilities: {
    list(): Promise<CapabilityProjection>;
    invokeAction(action: CapabilityAction): Promise<CapabilityProjection>;
  };
  workspaces: {
    list(): Promise<WorkspaceReference[]>;
    chooseAndBind(): Promise<WorkspaceReference | null>;
    chooseAndRelink(workspaceId: WorkspaceId): Promise<WorkspaceReference | null>;
    remove(workspaceId: WorkspaceId, confirmation: Confirmation): Promise<void>;
    revalidate(workspaceId: WorkspaceId): Promise<WorkspaceReference>;
  };
  backup: {
    describe(): Promise<BackupDisclosure>;
    chooseAndCreate(acknowledgement: BackupAcknowledgement): Promise<BackupResult | null>;
    chooseAndValidateRestore(): Promise<RestorePreview | null>;
    commitRestore(restoreToken: RestoreToken, confirmation: Confirmation): Promise<RestoreResult>;
    cancelRestore(restoreToken: RestoreToken): Promise<void>;
  };
}
```

Prohibited facade shapes include:

- `send(channel, value)`;
- `invoke(method, params)`;
- `callRpc(method, json)`;
- `on(channel, callback)`;
- `exec`, `spawn`, `shell`, `filesystem.*`, or arbitrary path methods;
- exposing `ipcRenderer`, Electron event objects, request/mutation IDs, RPC envelopes, raw serialized runtime lines, or sidecar streams.

Every subscription:

- wraps and discards the Electron event object;
- accepts only validated public-safe payloads;
- returns an idempotent unsubscribe function;
- is removed on pane unmount, subscription close, renderer reload, and window close;
- does not create a new sidecar subscription when another renderer consumer can share the same session projection.

## 4. Electron main handler rules

Each invoking preload method maps to one exact internal channel and one exact sidecar RPC method or main-owned native flow. `app.subscribeStatus` and `interaction.subscribe` are the only non-invoking methods: they register validated local bindings to already-negotiated sidecar notifications/main lifecycle state, issue no RPC request or mutation, and retain the subscription cleanup rules in Section 3.

For every invocation, main must:

1. validate `event.senderFrame` is the trusted top frame of the current application window and matches the expected packaged/development URL policy;
2. reject detached, navigated, subframe, unknown-window, or stale senders;
3. validate all input by a bounded explicit schema before native dialog or sidecar dispatch;
4. generate private RPC request and mutation IDs;
5. keep absolute paths returned by native pickers out of the renderer result;
6. normalize sidecar errors into the typed public-safe error union;
7. reject all pending renderer promises on sidecar failure/window teardown;
8. prevent handler registration duplication across window recreation/tests.

Native chooser flows:

- `chooseAndBind`/`chooseAndRelink` use a directory picker owned by main. Cancellation returns `null` and performs no mutation.
- `chooseAndCreate` uses a save destination picker only after the renderer acknowledges the exact unencrypted-backup disclosure. The returned path is sent privately to the sidecar and never returned.
- `chooseAndValidateRestore` uses a file picker. The renderer receives only a safe manifest summary and opaque restore token, never the archive path or unsafe entry names.

## 5. Typed public-safe errors

Renderer-facing failures use a discriminated union such as:

```typescript
type DesktopRecovery =
  | "retry"
  | "restart_runtime"
  | "relink_workspace"
  | "wait"
  | "close_active_interaction"
  | "contact_support";

type DesktopError = {
  category:
    | "unavailable"
    | "incompatible"
    | "invalid_input"
    | "not_found"
    | "conflict"
    | "busy"
    | "invalid_state"
    | "workspace_relink_required"
    | "unsafe_input"
    | "cancelled"
    | "deadline_exceeded"
    | "durability_unsupported"
    | "publication_failed"
    | "internal_failure";
  messageKey: string;
  retryable: boolean;
  recovery?: DesktopRecovery;
};
```

Electron main validates the exact RPC code/category pair and maps it through this total table; a row with two variants is selected only by the exact RPC `retryable` value shown:

| RPC code/category | `DesktopError.category` | `retryable` | Required recovery |
|---|---|---:|---|
| `-32700 parse_error` | `incompatible` | false | `restart_runtime` |
| `-32600 invalid_request` | `incompatible` | false | `restart_runtime` |
| `-32601 method_not_found` | `incompatible` | false | `contact_support` |
| `-32602 invalid_params` | `invalid_input` | false | absent |
| `-32603 internal_failure` | `internal_failure` | true | `restart_runtime` |
| `-32001 incompatible_protocol` | `incompatible` | false | `contact_support` |
| `-32002 not_found` | `not_found` | false | absent |
| `-32003 conflict` | `conflict` | true | `retry` |
| `-32004 busy` | `busy` | true | `wait` |
| `-32005 invalid_state` | `invalid_state` | false | `close_active_interaction` |
| `-32006 workspace_relink_required` | `workspace_relink_required` | false | `relink_workspace` |
| `-32007 unsafe_input` | `unsafe_input` | false | absent |
| `-32008 unavailable` | `unavailable` | true | `retry` |
| `-32008 unavailable` | `unavailable` | false | `contact_support` |
| `-32009 cancelled` | `cancelled` | false | absent |
| `-32010 deadline_exceeded` | `deadline_exceeded` | true | `retry` |
| `-32011 durability_unsupported` | `durability_unsupported` | false | `contact_support` |
| `-32012 publication_failed` | `publication_failed` | true | `retry` |
| `-32012 publication_failed` | `publication_failed` | false | `restart_runtime` |

Backup/restore internal causes select only the following existing wire rows and fixed allowlisted localization keys; the internal cause name never appears as `error.data.category`:

| Internal cause | Exact RPC code/category | `retryable` | Required recovery | Fixed `messageKey` |
|---|---|---:|---|---|
| `unsafe_archive` | `-32007 unsafe_input` | false | absent | `backup.error.unsafe_archive` |
| `incompatible_backup` | `-32001 incompatible_protocol` | false | `contact_support` | `backup.error.incompatible` |
| `integrity_failed` | `-32007 unsafe_input` | false | absent | `backup.error.integrity_failed` |
| `limit_exceeded` | `-32007 unsafe_input` | false | absent | `backup.error.limit_exceeded` |
| `profile_busy` | `-32004 busy` | true | `wait` | `backup.error.profile_busy` |
| `insufficient_space` | `-32008 unavailable` | true | `retry` | `backup.error.insufficient_space` |
| `durability_unsupported` | `-32011 durability_unsupported` | false | `contact_support` | `restore.error.durability_unsupported` |
| `publication_failed` with exact prior authority usable | `-32012 publication_failed` | true | `retry` | `restore.error.publication_failed_retryable` |
| `publication_failed` in restart-required failed state | `-32012 publication_failed` | false | `restart_runtime` | `restore.error.publication_failed_restart` |
| `rolled_back` to an exact usable prior authority | `-32012 publication_failed` | true | `retry` | `restore.error.rolled_back` |
| `cancelled` | `-32009 cancelled` | false | absent | `backup.error.cancelled` |
| unknown/unrecognized internal cause | `-32603 internal_failure` | true | `restart_runtime` | `desktop.error.internal_failure` |

`messageKey` is the fixed allowlisted localization key for the selected general row and, where applicable, the exact backup/restore cause row above. The unknown-cause row is the sole containment fallback: it uses exactly `desktop.error.internal_failure`, never a cause-derived or raw key. Electron main validates and maps the RPC recovery field exhaustively to the exact `DesktopRecovery` value required by the selected row; it never accepts a missing required recovery, a recovery where the row requires absence, a combined/unknown string, an unknown code/category pair, or a lossy conversion. The error/status payload does not contain raw sidecar messages, exception text, paths, credentials, rule expressions, provider responses, rejected sensitive values, PIDs, or stack traces. Authorized conversation/history and referenced-artifact content may losslessly contain user-, model-, or tool-produced sensitive values; adapters must route that content only to the corresponding content surface and never copy it into errors, status, audit, logs, diagnostics, or manifest metadata. Localization occurs in shared presentation from `messageKey`, not by rendering raw errors.

## 6. Shared presentation host

The reusable presentation layer depends on a transport-neutral, capability-aware interface rather than `ApiClient`, HTTP semantics, Electron, or sidecar RPC.

```typescript
interface CoworkPresentationHost {
  readonly surface: "web" | "desktop";
  readonly capabilities: PresentationCapabilities;

  sessions: SessionPresentationService;
  interaction: InteractionPresentationService;
  inspection: InspectionPresentationService;
  settings: SettingsPresentationService;
  files: FilePresentationService;
  desktop?: DesktopPresentationService;
}
```

The interface semantics are:

- session list/history/create/resume/fork/rename/star/delete/search and profile-local project grouping use presentation-safe models;
- run streaming/subscription emits the same normalized `RawEvent` semantics already consumed by the chat reducer;
- approval/question/cancel use exact pending request/session identity;
- cost/budget/agent-control/capability/workspace/upload/artifact values remain host-owned projections;
- unsupported operations are represented in `PresentationCapabilities` and unavailable states, not with throwing placeholders or fabricated success;
- Desktop-only workspace picker, pane/profile backup, and restore operations live under `desktop` and are absent on Web;
- Web-only transport concerns such as bearer handling, HTTP status, SSE/WS reconnect, or upload endpoints stay inside `WebPresentationHost` adapters.

## 7. Adapter responsibilities

### `WebPresentationHost`

- Composes existing `ApiClient` and `SessionTransport`.
- Preserves current `/v1`, SSE/WS, generated contract, auth, upload, and error behavior.
- Requires no Desktop/Electron package at runtime.
- Produces byte-/shape-equivalent reducer inputs for existing Web flows.

### `DesktopPresentationHost`

- Composes only the typed `window.loopplaneDesktop` facade.
- Converts typed interaction notifications to the existing chat reducer's normalized event input without changing event meaning.
- Maintains renderer-local pane drafts/focus/view state, but never accepted runtime policy/lease/principal/path state.
- Does not pretend sidecar RPC is HTTP and does not import `ApiClient`.

### Shared presentation

Owns:

- app shell and layout composition;
- message list and chat reducer behavior;
- approval/question dialogs;
- settings, inspection, agent controls, capability unavailable states;
- localization, theme, syntax highlighting, focus management, high zoom, forced colors, and reduced motion;
- loading, empty, retry, crash/unavailable, and read-only states.

Does not own:

- process lifecycle, path selection/canonicalization, principal identity, RPC/IPC IDs;
- tool/Gateway/permission/plan/budget/workspace enforcement;
- backup archive I/O or profile mutation;
- Web auth/network details;
- Desktop single-active lease authority.

## 8. Multi-pane presentation contract

- One window may host multiple panes.
- V1 opens a persisted session in at most one pane; requesting the same session focuses that pane. Fork creates a distinct session/pane.
- Each pane retains bounded renderer-local draft, focus token, scroll/view, and selected inspection tab. Unsent drafts survive pane conflicts during the running app but are intentionally excluded from profile persistence and backup.
- The host projection names the active interactive session/pane correlation. Renderer state may mirror it but cannot grant ownership.
- While one pane owns interaction, all other panes remain history/inspection capable and submission-disabled with a safe owner explanation.
- A rejected second submit preserves every pane's draft, history, focus, and inspection state.
- Closing or reordering a non-owner pane does not affect the run.
- Closing the owner pane requires an explicit choice to keep the run visible elsewhere or cancel/release safely; silent orphan ownership is prohibited.

## 9. Accessibility and interaction requirements

Shared presentation preserves existing bilingual and accessibility behavior and adds pane-specific rules:

- deterministic keyboard commands for next/previous pane, composer, sidebar, and close/fork actions;
- no global shortcut while a text field/dialog consumes the same keystroke unless explicitly documented;
- visible focus and a safe fallback target when a pane/dialog/sidebar unmounts;
- focus restoration to the invoking control where it still exists, otherwise to the active pane heading/composer;
- dialogs retain modal focus behavior and Escape/cancel semantics;
- at high zoom, panes collapse/reflow without hiding the active composer or terminal outcome;
- forced-color and reduced-motion modes do not rely on color or motion alone for active/read-only/waiting state.

Packaged Windows smoke reuses ordinary visible controls rather than adding a hidden renderer bridge. Because Electron/Chromium does not guarantee that DOM attributes map to a WPF-style UIA `AutomationId`, the contract locates controls only by exact `AutomationElement.NameProperty` plus `AutomationElement.ControlTypeProperty`: `LoopPlane smoke runtime status`/Group, `LoopPlane smoke new session`/Button, `LoopPlane smoke prompt`/Edit, `LoopPlane smoke submit`/Button, `LoopPlane smoke latest outcome`/Group, `LoopPlane smoke session list`/List, and `LoopPlane smoke runtime diagnostic`/Group. Fixed non-localized names are applied to the same controls only in packaged-smoke mode, while normal launches retain localized accessibility. Windows packaged-smoke mode calls `app.setAccessibilitySupportEnabled(true)` after `app.whenReady()` and before BrowserWindow creation; normal launches do not force it. Artifact preflight must prove every pair exists exactly once in the actual packaged accessibility tree, and may not fall back to AutomationId or localized visible text. These controls expose only ordinary visible status/input/action/outcome semantics—never paths, principal/request/mutation IDs, raw RPC/IPC, process handles, or model/tool controls. Production must not enable CDP, DevTools/remote debugging, DOM injection, or a local automation listener for smoke.

## 10. Regression and compatibility obligations

Implementation must prove:

- no remaining raw renderer-to-sidecar channel or generic preload escape hatch;
- sender validation and schema rejection for every privileged operation;
- unsubscribe and teardown across pane/window/sidecar lifecycle;
- Web presentation retains existing behavior and contracts through `WebPresentationHost`;
- Desktop uses shared source through a deterministic clean-install build graph, not sibling `node_modules` accidents;
- no runtime dependency from Web to Electron or from Desktop renderer to Node;
- no change to Web `/v1`, generated client/public contracts, Event Bus, checkpoint schema, Gateway, or runtime defaults.
