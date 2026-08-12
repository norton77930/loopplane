/**
 * Renderer typings for the frozen preload facade (078 T029).
 */

export type DesktopStatus = {
  ready?: boolean;
  initialized?: boolean;
  shutdown?: boolean;
  [key: string]: unknown;
};

export type InteractionHandle = {
  session_id: string;
  subscription_id: string;
  pane_id?: string | null;
};

export type AcceptedRun = {
  accepted?: boolean;
  subscription_id?: string;
  session_id?: string;
  termination_reason?: string;
  turns_taken?: number;
  [key: string]: unknown;
};

export type TurnAuditEntry = {
  audit_id: string;
  session_id: string;
  turn_ordinal: number;
  checkpoint_sequence: number;
  recorded_at: string | null;
  state: "completed" | "interrupted";
  termination_reason: string | null;
  turns_taken: number | null;
};

export type TurnAuditPage = {
  session_id: string;
  entries: TurnAuditEntry[];
  next_cursor: string | null;
};

export type BackupDescription = {
  disclosure: string;
  includes: string[];
  excludes: string[];
  format: string;
  schema_version: number;
};

export type BackupCreateResult = {
  ok: boolean;
  finalized: boolean;
  entry_count: number;
  format: string;
  disclosure_applied: boolean;
};

export type RestoreSummary = {
  format: "loopplane.desktop.backup";
  version: { major: 1; minor: 0 };
  created_at: string;
  project_count: number;
  session_count: number;
  artifact_count: number;
  drafts_excluded: true;
  relink_required: true;
};

export type RestoreValidationResult = {
  restore_token: string;
  summary: RestoreSummary;
};

export type RestoreCommitResult = {
  ok: boolean;
  committed: boolean;
  relink_required: true;
};

export type LoopPlaneDesktopApi = {
  app: {
    status(): Promise<DesktopStatus>;
    shutdown(): Promise<{ ok?: boolean } | unknown>;
    subscribeStatus(handler: (event: unknown) => void): () => void;
  };
  sessions: {
    list(query?: { query?: string }): Promise<{ sessions: unknown[] }>;
    history(sessionId: string): Promise<unknown>;
    rename(sessionId: string, title: string): Promise<unknown>;
    setStarred(sessionId: string, starred: boolean): Promise<unknown>;
    delete(sessionId: string, confirmation: unknown): Promise<unknown>;
    fork(
      sessionId: string,
      confirmation: unknown,
      sourceSequence?: number,
    ): Promise<unknown>;
    createInteractive(input?: {
      paneId?: string;
      workspaceId?: string;
      workspace_id?: string;
    }): Promise<InteractionHandle>;
    resumeInteractive(input: {
      sessionId: string;
      paneId?: string;
      workspaceId?: string;
      workspace_id?: string;
    }): Promise<InteractionHandle>;
    releaseInteractive(subscriptionId: string): Promise<{ released?: boolean }>;
  };
  projects: {
    list(): Promise<{ projects: unknown[] }>;
    create(input: { label: string }): Promise<unknown>;
    rename(projectId: string, label: string): Promise<unknown>;
    remove(projectId: string): Promise<unknown>;
    assignSession(
      projectId: string | null,
      sessionId: string,
    ): Promise<unknown>;
  };
  workspaces: {
    list(): Promise<{ workspaces: unknown[] }>;
    chooseAndBind(input?: { label?: string }): Promise<unknown>;
    chooseAndRelink(workspaceId: string): Promise<unknown>;
    remove(workspaceId: string): Promise<unknown>;
    revalidate(workspaceId: string): Promise<unknown>;
  };
  inspection: {
    get(sessionId: string | null): Promise<unknown>;
  };
  agentControls: {
    get(sessionId: string): Promise<unknown>;
  };
  capabilities: {
    list(): Promise<unknown>;
    invokeAction(capabilityId: string, action: string): Promise<unknown>;
  };
  audit: {
    list(
      sessionId: string,
      cursor?: string,
      limit?: number,
    ): Promise<TurnAuditPage>;
  };
  backup: {
    describe(): Promise<BackupDescription>;
    chooseAndCreate(input: {
      acknowledgement: boolean;
    }): Promise<BackupCreateResult | null>;
    chooseAndValidateRestore(): Promise<RestoreValidationResult | null>;
    commitRestore(
      restoreToken: string,
      confirmation: boolean,
    ): Promise<RestoreCommitResult>;
    cancelRestore(restoreToken: string): Promise<void>;
  };
  interaction: {
    submit(
      subscriptionId: string,
      input: { prompt: string; permissionMode?: string },
    ): Promise<AcceptedRun>;
    cancel(subscriptionId: string): Promise<unknown>;
    answerApproval(
      subscriptionId: string,
      requestId: string,
      decision: { allow: boolean },
    ): Promise<unknown>;
    answerQuestion(
      subscriptionId: string,
      requestId: string,
      answer: { answers: string[] },
    ): Promise<unknown>;
    subscribe(
      subscriptionId: string,
      handler: (event: unknown) => void,
    ): () => void;
  };
};

declare global {
  interface Window {
    /** Frozen typed facade from preload. */
    loopplaneDesktop?: LoopPlaneDesktopApi;
  }
}

export {};
