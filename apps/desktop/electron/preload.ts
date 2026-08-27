/**
 * Typed, frozen preload facade (078 T029).
 *
 * Exposes `window.loopplaneDesktop` with operation-specific methods only.
 * Never exposes ipcRenderer, channel strings, raw RPC, request IDs, or Node.
 */

import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

import { unwrapBackupRestoreEnvelope } from "./backup-restore-ipc";
import { IPC } from "./ipc-channels";

type StatusHandler = (event: unknown) => void;
type InteractionHandler = (event: unknown) => void;

function invokeBackupRestore(
  channel: string,
  ...args: unknown[]
): Promise<unknown> {
  return ipcRenderer.invoke(channel, ...args).then(
    (value) => unwrapBackupRestoreEnvelope(value),
    () => unwrapBackupRestoreEnvelope(undefined),
  );
}

function wrapSubscribe(
  channel: string,
  handler: (payload: unknown) => void,
): () => void {
  const listener = (_event: IpcRendererEvent, payload: unknown) => {
    // Discard Electron event object; only public-safe payload reaches renderer.
    handler(payload);
  };
  ipcRenderer.on(channel, listener);
  let active = true;
  return () => {
    if (!active) return;
    active = false;
    ipcRenderer.removeListener(channel, listener);
  };
}

const loopplaneDesktop = Object.freeze({
  app: Object.freeze({
    status: (): Promise<unknown> => ipcRenderer.invoke(IPC.appStatus),
    shutdown: (): Promise<unknown> => ipcRenderer.invoke(IPC.appShutdown),
    subscribeStatus: (handler: StatusHandler): (() => void) =>
      wrapSubscribe(IPC.statusEvent, handler),
  }),
  sessions: Object.freeze({
    list: (query?: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionList, query ?? {}),
    history: (sessionId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionHistory, { sessionId }),
    rename: (sessionId: string, title: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionRename, { sessionId, title }),
    setStarred: (sessionId: string, starred: boolean): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionSetStarred, { sessionId, starred }),
    delete: (sessionId: string, confirmation: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionDelete, { sessionId, confirmation }),
    fork: (
      sessionId: string,
      confirmation: unknown,
      sourceSequence?: number,
    ): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionFork, {
        sessionId,
        confirmation,
        sourceSequence: sourceSequence ?? 0,
      }),
    createInteractive: (input: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionCreateInteractive, input),
    resumeInteractive: (input: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionResumeInteractive, input),
    releaseInteractive: (subscriptionId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.sessionReleaseInteractive, {
        subscriptionId,
      }),
  }),
  projects: Object.freeze({
    list: (): Promise<unknown> => ipcRenderer.invoke(IPC.projectList),
    create: (input: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.projectCreate, input),
    rename: (projectId: string, label: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.projectRename, { projectId, label }),
    remove: (projectId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.projectRemove, { projectId }),
    assignSession: (
      projectId: string | null,
      sessionId: string,
    ): Promise<unknown> =>
      ipcRenderer.invoke(IPC.projectAssignSession, { projectId, sessionId }),
  }),
  workspaces: Object.freeze({
    list: (): Promise<unknown> => ipcRenderer.invoke(IPC.workspaceList),
    chooseAndBind: (input?: unknown): Promise<unknown> =>
      ipcRenderer.invoke(IPC.workspaceChooseAndBind, input ?? {}),
    chooseAndRelink: (workspaceId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.workspaceChooseAndRelink, { workspaceId }),
    remove: (workspaceId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.workspaceRemove, { workspaceId }),
    revalidate: (workspaceId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.workspaceRevalidate, { workspaceId }),
  }),
  inspection: Object.freeze({
    get: (sessionId: string | null): Promise<unknown> =>
      ipcRenderer.invoke(IPC.inspectionGet, { sessionId }),
  }),
  agentControls: Object.freeze({
    get: (sessionId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.agentControlsGet, { sessionId }),
  }),
  capabilities: Object.freeze({
    list: (): Promise<unknown> => ipcRenderer.invoke(IPC.capabilitiesList),
    invokeAction: (capabilityId: string, action: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.capabilitiesInvokeAction, {
        capabilityId,
        action,
      }),
  }),
  cost: Object.freeze({
    get: (sessionId: string | null): Promise<unknown> =>
      ipcRenderer.invoke(IPC.costGet, { sessionId }),
  }),
  capabilityManagement: Object.freeze({
    mcp: Object.freeze({
      list: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpList),
      get: (mcpId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpGet, { mcpId }),
      upsert: (input: {
        name: string;
        transport: string;
        url: string;
        mode?: "none" | "interactive";
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpUpsert, {
          name: input.name,
          transport: input.transport,
          url: input.url,
          mode: input.mode,
        }),
      reconnect: (mcpId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpReconnect, { mcpId }),
      disconnect: (mcpId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpDisconnect, { mcpId }),
      remove: (mcpId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMcpDelete, { mcpId }),
    }),
    skills: Object.freeze({
      list: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilitySkillList),
      get: (skillId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilitySkillGet, { skillId }),
      write: (input: {
        name: string;
        description: string;
        instructions: string;
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilitySkillWrite, {
          name: input.name,
          description: input.description,
          instructions: input.instructions,
        }),
      import: (input: {
        name: string;
        description: string;
        instructions: string;
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilitySkillImport, {
          name: input.name,
          description: input.description,
          instructions: input.instructions,
        }),
      remove: (skillId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilitySkillDelete, { skillId }),
    }),
    memory: Object.freeze({
      list: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMemoryList),
      get: (memoryId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMemoryGet, { memoryId }),
      write: (input: {
        name: string;
        kind: string;
        description: string;
        content: string;
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMemoryWrite, {
          name: input.name,
          kind: input.kind,
          description: input.description,
          content: input.content,
        }),
      remove: (memoryId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.capabilityMemoryDelete, { memoryId }),
    }),
  }),
  governance: Object.freeze({
    schedules: Object.freeze({
      list: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleList),
      get: (scheduleId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleGet, { scheduleId }),
      upsert: (input: {
        name: string;
        description: string;
        trigger: string;
        instruction: string;
        enabled: boolean;
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleUpsert, {
          name: input.name,
          description: input.description,
          trigger: input.trigger,
          instruction: input.instruction,
          enabled: input.enabled,
        }),
      enable: (scheduleId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleEnable, { scheduleId }),
      disable: (scheduleId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleDisable, { scheduleId }),
      runNow: (scheduleId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleRunNow, { scheduleId }),
      remove: (scheduleId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceScheduleDelete, { scheduleId }),
    }),
    contexts: Object.freeze({
      list: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceContextList),
      get: (contextId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceContextGet, { contextId }),
      upsert: (input: {
        name: string;
        description: string;
        workspace_label: string;
      }): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceContextUpsert, {
          name: input.name,
          description: input.description,
          workspaceLabel: input.workspace_label,
        }),
      bind: (sessionId: string, contextId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceContextBind, { sessionId, contextId }),
      remove: (contextId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceContextDelete, { contextId }),
    }),
    modelDefault: Object.freeze({
      get: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceModelDefaultGet),
      set: (modelId: string): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceModelDefaultSet, { modelId }),
      clear: (): Promise<unknown> =>
        ipcRenderer.invoke(IPC.governanceModelDefaultClear),
    }),
  }),
  command: Object.freeze({
    execute: (text: string, sessionId: string | null): Promise<unknown> =>
      ipcRenderer.invoke(IPC.commandExecute, { text, sessionId }),
  }),
  audit: Object.freeze({
    list: (sessionId: string, cursor?: string, limit?: number) =>
      ipcRenderer.invoke(IPC.auditList, {
        sessionId,
        ...(cursor === undefined ? {} : { cursor }),
        ...(limit === undefined ? {} : { limit }),
      }),
  }),
  backup: Object.freeze({
    describe: (): Promise<unknown> =>
      invokeBackupRestore(IPC.backupDescribe),
    chooseAndCreate: (input: { acknowledgement: boolean }): Promise<unknown> =>
      invokeBackupRestore(IPC.backupCreate, {
        acknowledgement: input.acknowledgement,
      }),
    chooseAndValidateRestore: (): Promise<unknown> =>
      invokeBackupRestore(IPC.restoreValidate),
    commitRestore: (
      restoreToken: string,
      confirmation: boolean,
    ): Promise<unknown> =>
      invokeBackupRestore(IPC.restoreCommit, { restoreToken, confirmation }),
    cancelRestore: (restoreToken: string): Promise<void> =>
      invokeBackupRestore(IPC.restoreCancel, { restoreToken }).then(() => undefined),
  }),
  // Provider settings. `get` answers with a public view only — the stored key
  // never crosses this boundary in either direction except on an explicit save.
  providers: Object.freeze({
    get: (): Promise<unknown> => ipcRenderer.invoke(IPC.providersGet),
    save: (input: {
      provider: string;
      modelId: string;
      apiKey: string | null;
    }): Promise<unknown> =>
      ipcRenderer.invoke(IPC.providersSave, {
        provider: input.provider,
        modelId: input.modelId,
        apiKey: input.apiKey,
      }),
    clear: (): Promise<unknown> => ipcRenderer.invoke(IPC.providersClear),
    restart: (): Promise<unknown> => ipcRenderer.invoke(IPC.providersRestart),
    catalog: (): Promise<unknown> => ipcRenderer.invoke(IPC.providersCatalog),
  }),
  interaction: Object.freeze({
    submit: (
      subscriptionId: string,
      input: { prompt: string; permissionMode?: string },
    ): Promise<unknown> =>
      ipcRenderer.invoke(IPC.interactionSubmit, {
        subscriptionId,
        prompt: input.prompt,
        ...(input.permissionMode === undefined
          ? {}
          : { permissionMode: input.permissionMode }),
      }),
    cancel: (subscriptionId: string): Promise<unknown> =>
      ipcRenderer.invoke(IPC.interactionCancel, { subscriptionId }),
    answerApproval: (
      subscriptionId: string,
      requestId: string,
      decision: { allow: boolean },
    ): Promise<unknown> =>
      ipcRenderer.invoke(IPC.interactionAnswerApproval, {
        subscriptionId,
        requestId,
        allow: decision.allow,
      }),
    answerQuestion: (
      subscriptionId: string,
      requestId: string,
      answer: { answers: string[] },
    ): Promise<unknown> =>
      ipcRenderer.invoke(IPC.interactionAnswerQuestion, {
        subscriptionId,
        requestId,
        answers: answer.answers,
      }),
    subscribe: (
      subscriptionId: string,
      handler: InteractionHandler,
    ): (() => void) =>
      // Local notification binding only — no RPC at subscribe/unsubscribe time.
      wrapSubscribe(IPC.interactionEvent, (payload) => {
        if (!payload || typeof payload !== "object") return;
        const params = (payload as { params?: unknown }).params;
        if (!params || typeof params !== "object") return;
        const payloadSubscriptionId = (
          params as { subscription_id?: unknown }
        ).subscription_id;
        if (payloadSubscriptionId !== subscriptionId) return;
        handler(payload);
      }),
  }),
});

contextBridge.exposeInMainWorld("loopplaneDesktop", loopplaneDesktop);

// Legacy bridge retained only if tests still probe window.api — omit raw tunnel.
// Do not re-expose send/onLine (FR-003).
