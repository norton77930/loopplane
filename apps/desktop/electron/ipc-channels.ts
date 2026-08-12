/**
 * Internal Electron IPC channel allowlist (078 T028).
 * Renderer never sees these strings through preload.
 */

export const IPC = {
  appStatus: "lp:app:status",
  appShutdown: "lp:app:shutdown",
  sessionCreateInteractive: "lp:session:createInteractive",
  sessionResumeInteractive: "lp:session:resumeInteractive",
  sessionReleaseInteractive: "lp:session:releaseInteractive",
  sessionList: "lp:session:list",
  sessionHistory: "lp:session:history",
  sessionRename: "lp:session:rename",
  sessionSetStarred: "lp:session:setStarred",
  sessionDelete: "lp:session:delete",
  sessionFork: "lp:session:fork",
  projectList: "lp:project:list",
  projectCreate: "lp:project:create",
  projectRename: "lp:project:rename",
  projectRemove: "lp:project:remove",
  projectAssignSession: "lp:project:assignSession",
  workspaceList: "lp:workspace:list",
  workspaceChooseAndBind: "lp:workspace:chooseAndBind",
  workspaceChooseAndRelink: "lp:workspace:chooseAndRelink",
  workspaceRemove: "lp:workspace:remove",
  workspaceRevalidate: "lp:workspace:revalidate",
  interactionSubmit: "lp:interaction:submit",
  interactionCancel: "lp:interaction:cancel",
  interactionAnswerApproval: "lp:interaction:answerApproval",
  interactionAnswerQuestion: "lp:interaction:answerQuestion",
  inspectionGet: "lp:inspection:get",
  agentControlsGet: "lp:agentControls:get",
  capabilitiesList: "lp:capabilities:list",
  capabilitiesInvokeAction: "lp:capabilities:invokeAction",
  auditList: "lp:audit:list",
  backupDescribe: "lp:backup:describe",
  backupCreate: "lp:backup:create",
  restoreValidate: "lp:restore:validate",
  restoreCommit: "lp:restore:commit",
  restoreCancel: "lp:restore:cancel",
  /** Main -> renderer push (not invoke). */
  statusEvent: "lp:app:statusEvent",
  interactionEvent: "lp:interaction:event",
} as const;

export type IpcChannel = (typeof IPC)[keyof typeof IPC];
