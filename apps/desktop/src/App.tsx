/**
 * Desktop composition: multi-pane shell + single active lease (T031/T045/T053).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  claimLease,
  closePane,
  CoworkShell,
  CapabilitySettingsView,
  AgentControlsSettings,
  createEmptyWorkspace,
  focusPane,
  getFocusedPane,
  InspectionSidebar,
  RuntimeUnavailable,
  openPane,
  releaseLease,
  setPaneDraft,
  type AuditEntry,
  type PaneWorkspaceState,
  type PresentationAgentControls,
  type PresentationCapability,
  type PresentationInspection,
} from "@loopplane/cowork-presentation";
import { createDesktopPresentationHost } from "./presentation-host";
import { ApprovalDialog } from "@web/components/ApprovalDialog";
import { MessageList } from "@web/components/MessageList";
import { QuestionDialog } from "@web/components/QuestionDialog";
import { errored, initialState, reduce, userPrompt } from "@web/state/chat";
import type { RawEvent } from "@web/api/types";

import { BackupRestoreView } from "./components/BackupRestoreView";
import { SessionSidebar } from "./components/SessionSidebar";
import type {
  ProjectView,
  SessionSummaryView,
  SidecarTransport,
  WorkspaceView,
} from "./sidecar";

export type DesktopShellPhase =
  | "ready"
  | "unavailable"
  | "incompatible"
  | "starting"
  | "running"
  | "cancelling"
  | "outcome"
  | "error";

export type AppProps = {
  transport: SidecarTransport | null;
  initialPhase?: DesktopShellPhase;
  resumeSessionId?: string | null;
};

export function App({
  transport,
  initialPhase = "ready",
  resumeSessionId = null,
}: AppProps) {
  const [state, setState] = useState(initialState);
  const [input, setInput] = useState("");
  const [phase, setPhase] = useState<DesktopShellPhase>(
    transport ? initialPhase : "unavailable",
  );
  const [outcomeLabel, setOutcomeLabel] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummaryView[]>([]);
  const [projects, setProjects] = useState<ProjectView[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceView[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    resumeSessionId,
  );
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(
    null,
  );
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [paneWorkspace, setPaneWorkspace] = useState<PaneWorkspaceState>(() =>
    createEmptyWorkspace(),
  );
  const [ownerClosePaneId, setOwnerClosePaneId] = useState<string | null>(null);
  const [inspectLines, setInspectLines] = useState<string[]>([]);
  const [inspection, setInspection] = useState<PresentationInspection | null>(null);
  const [agentControls, setAgentControls] = useState<PresentationAgentControls | null>(null);
  const [capabilities, setCapabilities] = useState<PresentationCapability[] | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showBackupRestore, setShowBackupRestore] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditFailed, setAuditFailed] = useState(false);
  const [runtimeDiagnostic, setRuntimeDiagnostic] = useState<string | null>(null);
  /** Renderer-transient one-run draft; only Host acceptance clears it. */
  const [permissionModeDraft, setPermissionModeDraft] = useState<string | null>(null);
  const mounted = useRef(true);
  const runActive = useRef(false);
  const pendingApproval = state.pendingApproval;
  const pendingQuestion = state.pendingQuestion;
  const focusedPane = getFocusedPane(paneWorkspace);
  const presentationHost = useRef(createDesktopPresentationHost());

  const refreshLists = useCallback(async () => {
    if (!transport) return;
    try {
      const [s, p, w] = await Promise.all([
        transport.listSessions(),
        transport.listProjects(),
        transport.listWorkspaces(),
      ]);
      if (!mounted.current) return;
      setSessions(s);
      setProjects(p);
      setWorkspaces(w);
      const available = w.find((x) => x.availability === "available");
      if (available) {
        setSelectedWorkspaceId((current) => current ?? available.id);
      }
    } catch {
      /* lists are best-effort */
    }
  }, [transport]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      void transport?.dispose?.();
    };
  }, [transport]);

  useEffect(() => {
    const api = window.loopplaneDesktop;
    if (!api?.app?.subscribeStatus) {
      if (!transport) {
        setRuntimeDiagnostic("Local runtime unavailable.");
      }
      return;
    }
    return api.app.subscribeStatus((event) => {
      const value = event as {
        method?: unknown;
        params?: { diagnostic?: unknown; state?: unknown };
      };
      if (value.method !== "runtime.state" || !mounted.current) {
        return;
      }
      if (value.params?.state === "ready") {
        setPhase("ready");
        setRuntimeDiagnostic(null);
        void refreshLists();
        return;
      }
      if (value.params?.state !== "failed") {
        return;
      }
      const publicDiagnostic = value.params.diagnostic;
      const diagnostic =
        typeof publicDiagnostic === "string" && publicDiagnostic.trim()
          ? publicDiagnostic
          : "Local runtime unavailable. Restart LoopPlane.";
      setPhase(
        diagnostic.toLocaleLowerCase().includes("incompatible")
          ? "incompatible"
          : "unavailable",
      );
      setRuntimeDiagnostic(diagnostic);
    });
  }, [transport, refreshLists]);

  useEffect(() => {
    if (
      !transport ||
      initialPhase === "unavailable" ||
      initialPhase === "incompatible"
    ) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const status = await transport.status?.();
        if (cancelled || !mounted.current) return;
        if (status && status.ready === false) {
          setPhase("starting");
          return;
        }
        setPhase((current) => (current === "starting" ? "ready" : current));
        setRuntimeDiagnostic(null);
        await refreshLists();
      } catch {
        if (!cancelled && mounted.current) setPhase("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialPhase, transport, refreshLists]);

  // Keep renderer draft pane-local and on transport only (never durable).
  useEffect(() => {
    transport?.setDraft?.(input);
    if (focusedPane) {
      setPaneWorkspace((ws) => setPaneDraft(ws, focusedPane.paneId, input));
    }
  }, [input, transport, focusedPane?.paneId]);

  // Open/focus a pane when active session changes.
  useEffect(() => {
    if (!activeSessionId) return;
    setPaneWorkspace((ws) => {
      const existing = ws.panes.find((p) => p.sessionId === activeSessionId);
      if (existing) return focusPane(ws, existing.paneId);
      const title =
        sessions.find((s) => s.session_id === activeSessionId)?.title ||
        activeSessionId.slice(0, 8);
      return openPane(ws, {
        paneId: `pane-${activeSessionId}`,
        sessionId: activeSessionId,
        title: title || activeSessionId.slice(0, 8),
      });
    });
  }, [activeSessionId, sessions]);

  // Host-authoritative inspection projection (T065/T066 subset).
  useEffect(() => {
    const host = presentationHost.current;
    if (!host || !activeSessionId) {
      setInspectLines([]);
      setInspection(null);
      setAgentControls(null);
      setCapabilities(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [insp, ac, caps] = await Promise.all([
          host.getInspection(activeSessionId),
          host.getAgentControls(activeSessionId),
          host.getCapabilities(),
        ]);
        if (cancelled || !mounted.current) return;
        setInspection(insp);
        setAgentControls(ac);
        setCapabilities(caps);
        const lines: string[] = [];
        lines.push(`Tools: ${insp.tools.length}`);
        lines.push(`Skills: ${insp.skills.length}`);
        lines.push(`Budget pricing: ${ac.budget.pricing}`);
        if (ac.defaultMode) lines.push(`Default mode: ${ac.defaultMode}`);
        if (insp.unavailable || ac.unavailable) {
          lines.push("Some inspection data unavailable");
        }
        setInspectLines(lines);
      } catch {
        if (!cancelled && mounted.current) {
          setInspection(null);
          setAgentControls(null);
          setCapabilities(null);
          setInspectLines(["Inspection unavailable"]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  useEffect(() => {
    const host = presentationHost.current;
    if (!showBackupRestore || !activeSessionId || !host) {
      setAuditEntries([]);
      setAuditLoading(false);
      setAuditFailed(false);
      return;
    }
    let cancelled = false;
    setAuditEntries([]);
    setAuditLoading(true);
    setAuditFailed(false);
    void host
      .getTurnAudit(activeSessionId)
      .then((page) => {
        if (!cancelled && mounted.current) setAuditEntries(page.entries);
      })
      .catch(() => {
        if (!cancelled && mounted.current) setAuditFailed(true);
      })
      .finally(() => {
        if (!cancelled && mounted.current) setAuditLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId, showBackupRestore]);

  async function invokeCapabilityAction(capabilityId: string, action: string) {
    const host = presentationHost.current;
    if (!host) return;
    try {
      setCapabilities(await host.invokeCapabilityAction(capabilityId, action));
    } catch {
      // The host action allowlist remains authoritative; retain the last safe projection.
    }
  }

  const applyEvent = useCallback((event: RawEvent) => {
    setState((current) => reduce(current, event));
    if (event.type === "approval-requested" || event.type === "question-asked") {
      setPhase("running");
      runActive.current = true;
      return;
    }
    if (event.type === "run-terminated") {
      const reason =
        typeof (event.payload as { reason?: string })?.reason === "string"
          ? (event.payload as { reason: string }).reason
          : "completed";
      setOutcomeLabel(reason);
      setPhase("outcome");
      runActive.current = false;
    }
  }, []);

  async function send(prompt: string) {
    if (!transport || !prompt.trim()) return;
    if (
      phase === "unavailable" ||
      phase === "incompatible" ||
      phase === "running" ||
      phase === "cancelling" ||
      phase === "starting"
    ) {
      return;
    }
    // Ensure focused pane holds the single interactive lease (presentation).
    const paneId =
      focusedPane?.paneId ??
      (activeSessionId ? `pane-${activeSessionId}` : "pane-main");
    const claimed = claimLease(
      focusedPane
        ? paneWorkspace
        : openPane(paneWorkspace, {
            paneId,
            sessionId: activeSessionId,
            title: "Session",
          }),
      paneId,
    );
    if (!claimed.ok) {
      setPhase("error");
      setOutcomeLabel(
        `Another pane is interactive (${claimed.ownerPaneId ?? "unknown"}).`,
      );
      return;
    }
    setPaneWorkspace(claimed.state);

    setPhase("starting");
    setOutcomeLabel(null);
    setState((current) => userPrompt(current, prompt));
    runActive.current = true;
    try {
      if (activeSessionId && !transport.activeSessionId) {
        await transport.resume(
          activeSessionId,
          selectedWorkspaceId ?? undefined,
        );
      }
      if (!mounted.current) return;
      setPhase("running");
      let lastEvent: RawEvent | null = null;
      for await (const event of transport.run(prompt, {
        workspaceId: selectedWorkspaceId ?? undefined,
        ...(permissionModeDraft === null
          ? {}
          : { permissionMode: permissionModeDraft }),
      })) {
        if (!mounted.current) break;
        lastEvent = event;
        applyEvent(event);
      }
      if (mounted.current && transport.activeSessionId) {
        setActiveSessionId(transport.activeSessionId);
      }
      if (mounted.current && runActive.current) {
        if (
          lastEvent?.type === "approval-requested" ||
          lastEvent?.type === "question-asked"
        ) {
          setPhase("running");
        } else if (lastEvent?.type !== "run-terminated") {
          setPhase("outcome");
          runActive.current = false;
        }
      }
      // A completed transport run proves the Host accepted this one-run option.
      setPermissionModeDraft(null);
      await refreshLists();
    } catch {
      if (!mounted.current) return;
      runActive.current = false;
      setState(errored);
      setPhase("error");
    }
  }

  function cancelRun() {
    if (!transport || !runActive.current) return;
    setPhase("cancelling");
    setState((current) => ({
      ...current,
      pendingApproval: undefined,
      pendingQuestion: undefined,
    }));
    transport.cancel();
  }

  async function selectSession(sessionId: string) {
    if (!transport || runActive.current) return;
    // Switching session keeps unsent draft in transport until cleared/sent.
    if (transport.activeSubscriptionId) {
      await transport.release();
    }
    setActiveSessionId(sessionId);
    setState(initialState);
    setPhase("ready");
    setOutcomeLabel(null);
  }

  async function newSession() {
    if (!transport || runActive.current) return;
    if (transport.activeSubscriptionId) {
      await transport.release();
    }
    setActiveSessionId(null);
    setState(initialState);
    setPhase("ready");
    setOutcomeLabel(null);
  }

  const blocked =
    phase === "unavailable" ||
    phase === "incompatible" ||
    phase === "running" ||
    phase === "cancelling" ||
    phase === "starting";

  const statusText = (() => {
    switch (phase) {
      case "unavailable":
        return "Local runtime unavailable.";
      case "incompatible":
        return "Local runtime is incompatible.";
      case "starting":
        return "Starting interaction…";
      case "running":
        return "Running…";
      case "cancelling":
        return "Cancelling…";
      case "outcome":
        return outcomeLabel ? `Outcome: ${outcomeLabel}` : "Run finished.";
      case "error":
        return "Disconnected — please retry.";
      default:
        return "Local runtime usable.";
    }
  })();

  const leftSidebar = (
    <SessionSidebar
      sessions={sessions}
      projects={projects}
      workspaces={workspaces}
      activeSessionId={activeSessionId}
      selectedWorkspaceId={selectedWorkspaceId}
      busy={blocked}
      onSelectSession={(id) => void selectSession(id)}
      onNewSession={() => void newSession()}
      onToggleStar={(id, starred) => {
        void transport?.setSessionStarred(id, starred).then(refreshLists);
      }}
      onDeleteSession={(id) => setConfirmDeleteId(id)}
      onForkSession={(id) => {
        void transport?.forkSession(id, true, 0).then(refreshLists);
      }}
      onCreateProject={() => {
        const label = window.prompt("Project label");
        if (label) void transport?.createProject(label).then(refreshLists);
      }}
      onRemoveProject={(id) => {
        void transport?.removeProject(id).then(refreshLists);
      }}
      onBindWorkspace={() => {
        void transport?.chooseAndBindWorkspace().then(refreshLists);
      }}
      onRelinkWorkspace={(id) => {
        void transport?.chooseAndRelinkWorkspace(id).then(refreshLists);
      }}
      onSelectWorkspace={setSelectedWorkspaceId}
    />
  );

  const mainBody = (
      <main className="app">
        <header className="desktop-topbar">
          <h1>LoopPlane Desktop</h1>
          <div
            className="runtime-status"
            role="group"
            aria-label="LoopPlane smoke runtime status"
            aria-live="polite"
            data-testid="runtime-status"
          >
            <span role="status">{statusText}</span>
          </div>
          <div className="desktop-topbar-actions">
            <button type="button" onClick={() => setShowSettings(true)}>
              Settings
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSettings(false);
                setShowBackupRestore(true);
              }}
            >
              Backup and restore
            </button>
          </div>
        </header>
        <RuntimeUnavailable
          active={
            phase === "unavailable" ||
            phase === "incompatible" ||
            phase === "error"
          }
        >
          {phase === "error"
            ? runtimeDiagnostic ?? "Disconnected — please retry."
            : phase === "unavailable" || phase === "incompatible"
              ? runtimeDiagnostic ?? statusText
              : "No runtime diagnostic."}
        </RuntimeUnavailable>
        {confirmDeleteId && (
          <div className="modal-backdrop">
            <div
              className="confirm-dialog"
              role="dialog"
              aria-label="Confirm delete"
            >
              <p>Delete this session? History will be removed.</p>
              <div className="confirm-dialog-actions">
                <button type="button" onClick={() => setConfirmDeleteId(null)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="danger"
                  onClick={() => {
                    void transport
                      ?.deleteSession(confirmDeleteId, true)
                      .then(async () => {
                        if (activeSessionId === confirmDeleteId) {
                          await newSession();
                        }
                        setConfirmDeleteId(null);
                        await refreshLists();
                      });
                  }}
                >
                  Confirm delete
                </button>
              </div>
            </div>
          </div>
        )}
        <MessageList
          entries={state.entries}
          loading={phase === "running" || phase === "starting"}
        />
        {pendingApproval && (
          <ApprovalDialog
            toolName={pendingApproval.toolName}
            onDecide={(decision) => {
              transport?.answerApproval(
                pendingApproval.requestId,
                decision.allow,
              );
              setState((current) => ({
                ...current,
                pendingApproval: undefined,
              }));
            }}
          />
        )}
        {pendingQuestion && (
          <QuestionDialog
            prompt={pendingQuestion.prompt}
            options={pendingQuestion.options}
            onAnswer={(answers) => {
              transport?.answerQuestion(pendingQuestion.requestId, answers);
              setState((current) => ({
                ...current,
                pendingQuestion: undefined,
              }));
            }}
            onClose={() =>
              setState((current) => ({
                ...current,
                pendingQuestion: undefined,
              }))
            }
          />
        )}
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
            setInput("");
            transport?.clearDraft?.();
          }}
        >
          <input
            aria-label="LoopPlane smoke prompt"
            placeholder="Message LoopPlane…"
            value={input}
            disabled={blocked || !transport}
            onChange={(event) => setInput(event.target.value)}
          />
          <button
            type="submit"
            aria-label="LoopPlane smoke submit"
            disabled={blocked || !transport}
          >
            Send
          </button>
          <button
            type="button"
            aria-label="cancel run"
            disabled={
              !transport ||
              (phase !== "running" && phase !== "starting")
            }
            onClick={() => cancelRun()}
          >
            Cancel
          </button>
        </form>
      </main>
  );

  return (
    <div className="desktop-shell" data-phase={phase}>
      {ownerClosePaneId && (
        <div className="modal-backdrop">
          <div
            className="confirm-dialog"
            role="dialog"
            aria-label="Close interactive pane"
          >
            <p>This pane owns the active interaction. Close and release it?</p>
            <div className="confirm-dialog-actions">
              <button type="button" onClick={() => setOwnerClosePaneId(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  void (async () => {
                    await transport?.release?.();
                    setPaneWorkspace((ws) => {
                      const released = releaseLease(ws, ownerClosePaneId);
                      return closePane(released, ownerClosePaneId);
                    });
                    setOwnerClosePaneId(null);
                    runActive.current = false;
                    setPhase("ready");
                  })();
                }}
              >
                Release and close
              </button>
            </div>
          </div>
        </div>
      )}
      <CoworkShell
        workspace={paneWorkspace}
        leftSidebar={leftSidebar}
        rightSidebar={
          <InspectionSidebar
            sessionId={focusedPane?.sessionId ?? activeSessionId}
            title={focusedPane?.title}
            mode={focusedPane?.mode ?? "read_only"}
            leaseOwner={Boolean(focusedPane?.leaseOwner)}
            inspection={inspection}
            agentControls={agentControls}
            capabilities={capabilities}
            lines={[
              ...(outcomeLabel ? [`Last outcome: ${outcomeLabel}`] : []),
              ...inspectLines,
            ]}
          />
        }
        onFocusPane={(paneId) => {
          setPaneWorkspace((ws) => focusPane(ws, paneId));
          const pane = paneWorkspace.panes.find((p) => p.paneId === paneId);
          if (pane?.sessionId) void selectSession(pane.sessionId);
        }}
        onClosePane={(paneId) => {
          setPaneWorkspace((ws) => closePane(ws, paneId));
        }}
        onRequestInteractive={(paneId) => {
          setPaneWorkspace((ws) => {
            const result = claimLease(ws, paneId);
            if (!result.ok) {
              setOutcomeLabel(
                `Busy: pane ${result.ownerPaneId ?? "?"} holds the lease`,
              );
              return ws;
            }
            return result.state;
          });
        }}
        onConfirmOwnerClose={(paneId) => setOwnerClosePaneId(paneId)}
      >
        {showBackupRestore ? (
          <BackupRestoreView
            host={presentationHost.current}
            auditEntries={auditEntries}
            auditLoading={auditLoading}
            auditFailed={auditFailed}
            onBack={() => setShowBackupRestore(false)}
          />
        ) : showSettings ? (
          <CapabilitySettingsView
            title="Capability settings"
            categoriesLabel="Settings categories"
            backLabel="Back to chat"
            tabs={[
              { id: "capabilities", label: "Capabilities" },
              { id: "agent-controls", label: "Agent controls" },
            ]}
            capabilities={capabilities}
            onCapabilityAction={invokeCapabilityAction}
            onBack={() => setShowSettings(false)}
            renderTab={(tab) =>
              tab === "agent-controls" ? (
                <AgentControlsSettings
                  projection={null}
                  hostProjection={agentControls}
                  loading={false}
                  failed={agentControls?.unavailable ?? false}
                  permissionModeDraft={permissionModeDraft}
                  onPermissionModeChange={setPermissionModeDraft}
                  onRefresh={() => undefined}
                />
              ) : (
                <p>Capability availability is provided by the local host.</p>
              )
            }
          />
        ) : (
          mainBody
        )}
      </CoworkShell>
    </div>
  );
}
