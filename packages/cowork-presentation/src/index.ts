/**
 * @loopplane/cowork-presentation — first-party shared presentation surface (078).
 *
 * Transport-neutral exports for Web and Desktop adapters. US4 (T061+) moves
 * chat/shell/settings components here; US3 exports multi-pane shell primitives.
 */

/** Package identity for workspace resolution smoke checks. */
export const COWORK_PRESENTATION_PACKAGE = "@loopplane/cowork-presentation" as const;

/** Scaffold marker: non-empty public surface before component extraction. */
export const COWORK_PRESENTATION_SCAFFOLD = true as const;

export type {
  PaneDraft,
  PaneId,
  PaneMode,
  PaneState,
  PaneWorkspaceState,
} from "./panes/types";
export {
  canSubmitFromPane,
  claimLease,
  closePane,
  createEmptyWorkspace,
  focusPane,
  getFocusedPane,
  openPane,
  releaseLease,
  setPaneDraft,
} from "./panes/state";
export {
  COMPOSER_MAX_HEIGHT,
  growTextarea,
  resetTextareaHeight,
  shouldSubmitOnKey,
} from "./composer";
export {
  ASKS_FIRST_POSTURE,
  paneReadOnlyReason,
  paneStateLabel,
  permissionPostureLabel,
  toolConsequence,
} from "./vocabulary";
export {
  applyTheme,
  initTheme,
  persistTheme,
  resolveTheme,
  storedTheme,
  systemTheme,
  toggleTheme,
} from "./theme";
export type { StoredTheme, Theme } from "./theme";
export { CoworkShell } from "./components/CoworkShell";
export type { CoworkShellProps } from "./components/CoworkShell";
export { RuntimeUnavailable } from "./components/RuntimeUnavailable";
export type { RuntimeUnavailableProps } from "./components/RuntimeUnavailable";
export { InspectionSidebar } from "./components/InspectionSidebar";
export type { InspectionSidebarProps } from "./components/InspectionSidebar";
export { AuditView } from "./components/AuditView";
export type { AuditEntry, AuditViewProps } from "./components/AuditView";
export { ApprovalDialog } from "./components/ApprovalDialog";
export type {
  ApprovalDecision,
  ApprovalDialogProps,
} from "./components/ApprovalDialog";
export { QuestionDialog } from "./components/QuestionDialog";
export type { QuestionDialogProps } from "./components/QuestionDialog";
export {
  dismissOnEscape,
  focusElement,
  prefersReducedMotion,
  REDUCED_MOTION_MEDIA,
  restoreFocus,
} from "./focus";
export type {
  CoworkPresentationHost,
  PresentationSubmitOptions,
  ProgressHandler,
} from "./host";
export {
  defaultCapabilityMap,
  isAllowlistedCapabilityAction,
} from "./host";
export type {
  PresentationAgentControls,
  PresentationAvailability,
  PresentationCapability,
  PresentationCapabilityId,
  PresentationCapabilityMap,
  PresentationInspection,
  PresentationSessionSummary,
} from "./models";
export { PRESENTATION_CAPABILITY_MAP } from "./models";
export {
  ZERO_USAGE,
  errored,
  initialState,
  reduce,
  userPrompt,
} from "./state/chat";
export type {
  ChatState,
  ConversationEntry,
  RawEvent,
  TokenUsage,
  UsageState,
} from "./state/chat";
export { AppShell } from "./components/AppShell";
export type { AppShellProps } from "./components/AppShell";
export { MessageList } from "./components/MessageList";
export type { MessageListProps } from "./components/MessageList";
export { InspectionPanel } from "./components/InspectionPanel";
export type {
  InspectionLoaders,
  InspectionMcpServer,
  InspectionMemoryEntry,
  InspectionSkill,
  InspectionTool,
} from "./components/InspectionPanel";
export { CapabilitySettingsView } from "./components/CapabilitySettingsView";
export type {
  CapabilitySettingsTab,
  CapabilitySettingsViewProps,
} from "./components/CapabilitySettingsView";
export { AgentControlsSettings } from "./components/settings/AgentControlsSettings";
export type {
  AgentControlsProjection,
  AgentControlsService,
  AgentControlsSettingsProps,
  SessionContextSummary,
  SessionCost,
  WorkspaceContext,
} from "./components/settings/AgentControlsSettings";
export { PresentationI18nProvider, useTranslation } from "./i18n/i18n";
export type { Translation, TranslationMessages } from "./i18n/i18n";
