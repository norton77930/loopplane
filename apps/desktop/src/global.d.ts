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
  cost: {
    get(sessionId: string | null): Promise<unknown>;
  };
  capabilityManagement: {
    mcp: {
      list(): Promise<unknown>;
      get(mcpId: string): Promise<unknown>;
      upsert(input: {
        name: string;
        transport: string;
        url: string;
      }): Promise<unknown>;
      reconnect(mcpId: string): Promise<unknown>;
      remove(mcpId: string): Promise<unknown>;
    };
    skills: {
      list(): Promise<unknown>;
      get(skillId: string): Promise<unknown>;
      write(input: {
        name: string;
        description: string;
        instructions: string;
      }): Promise<unknown>;
      import(input: {
        name: string;
        description: string;
        instructions: string;
      }): Promise<unknown>;
      remove(skillId: string): Promise<unknown>;
    };
    memory: {
      list(): Promise<unknown>;
      get(memoryId: string): Promise<unknown>;
      write(input: {
        name: string;
        kind: string;
        description: string;
        content: string;
      }): Promise<unknown>;
      remove(memoryId: string): Promise<unknown>;
    };
  };
  governance: {
    schedules: {
      list(): Promise<unknown>;
      get(scheduleId: string): Promise<unknown>;
      upsert(input: {
        name: string;
        description: string;
        trigger: string;
        instruction: string;
        enabled: boolean;
      }): Promise<unknown>;
      enable(scheduleId: string): Promise<unknown>;
      disable(scheduleId: string): Promise<unknown>;
      runNow(scheduleId: string): Promise<unknown>;
      remove(scheduleId: string): Promise<unknown>;
    };
    contexts: {
      list(): Promise<unknown>;
      get(contextId: string): Promise<unknown>;
      upsert(input: {
        name: string;
        description: string;
        workspace_label: string;
      }): Promise<unknown>;
      bind(sessionId: string, contextId: string): Promise<unknown>;
      remove(contextId: string): Promise<unknown>;
    };
    modelDefault: {
      get(): Promise<unknown>;
      set(modelId: string): Promise<unknown>;
      clear(): Promise<unknown>;
    };
  };
  command: {
    execute(text: string, sessionId: string | null): Promise<unknown>;
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
  providers: {
    get(): Promise<ProviderView | null>;
    save(input: {
      provider: string;
      modelId: string;
      apiKey: string | null;
    }): Promise<ProviderSaveResult>;
    clear(): Promise<{ ok: true }>;
    restart(): Promise<{ ok: true }>;
    catalog(): Promise<ProviderCatalogEntry[]>;
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

/** One curated model suggestion; `current` marks the configured id. */
export type ProviderCatalogModel = { id: string; current: boolean };

/** Curated models for one provider — a typing aid, never a gate. */
export type ProviderCatalogEntry = {
  provider: string;
  models: ProviderCatalogModel[];
};

/** The renderer's view of the stored provider setting — never the key itself. */
export type ProviderView = {
  provider: string;
  modelId: string;
  hasKey: boolean;
  keyHint: string | null;
};

export type ProviderSaveResult =
  | { ok: true }
  | {
      ok: false;
      reason:
        | "encryption_unavailable"
        | "invalid_provider"
        | "invalid_model_id"
        | "missing_key"
        | "write_failed";
    };

declare global {
  interface Window {
    /** Frozen typed facade from preload. */
    loopplaneDesktop?: LoopPlaneDesktopApi;
  }
}

export {};
