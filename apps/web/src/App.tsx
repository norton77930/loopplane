import { useEffect, useMemo, useRef, useState } from "react";

import type { ApprovalDecision } from "./api/client";
import type {
  AgentControlProjection,
  MonthlyCostView,
  RawEvent,
  SessionCostView,
  SessionSummary,
} from "./api/types";
import { AppShell } from "./components/AppShell";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { Attachments, type Attachment } from "./components/Attachments";
import { ChatHeader } from "./components/ChatHeader";
import { CapabilitySettingsView } from "./components/CapabilitySettingsView";
import { Composer } from "./components/Composer";
import { ErrorBanner } from "./components/ErrorBanner";
import { FollowUpSuggestions } from "./components/FollowUpSuggestions";
import { InspectionPanel } from "./components/InspectionPanel";
import { MessageList } from "./components/MessageList";
import { ModelSelector } from "./components/ModelSelector";
import { QuestionDialog } from "./components/QuestionDialog";
import { Sidebar } from "./components/Sidebar";
import { useToast } from "./components/Toast";
import {
  deriveFollowUpSuggestions,
  followUpSuggestionStaleKey,
} from "./followUpSuggestions";
import { useTranslation } from "./i18n/i18n";
import {
  createWebPresentationHost,
  type WebPresentationHost,
  type WebPresentationHostOptions,
} from "./presentation-host";
import { errored, initialState, reduce, userPrompt } from "./state/chat";
import {
  chooseActiveAfterDelete,
  loadPreferredModel,
  savePreferredModel,
} from "./state/sessions";

export function App({
  host: injectedHost,
  client,
  transport,
  onUnauthorized,
}: WebPresentationHostOptions & {
  host?: WebPresentationHost;
  onUnauthorized?: () => void;
}) {
  const [state, setState] = useState(initialState);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showInspect, setShowInspect] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(() =>
    loadPreferredModel(),
  );
  const [sessionModel, setSessionModel] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [composerDraft, setComposerDraft] = useState("");
  const [composerFocusToken, setComposerFocusToken] = useState(0);
  const [dismissedSuggestions, setDismissedSuggestions] = useState<string[]>([]);
  const [agentControls, setAgentControls] =
    useState<AgentControlProjection | null>(null);
  const [agentControlsLoading, setAgentControlsLoading] = useState(false);
  const [agentControlsFailed, setAgentControlsFailed] = useState(false);
  const [permissionModeDraft, setPermissionModeDraft] = useState<string | null>(
    null,
  );
  const [sessionCost, setSessionCost] = useState<SessionCostView | null>(null);
  const [monthlyCost, setMonthlyCost] = useState<MonthlyCostView | null>(null);
  const [sessionCostLoading, setSessionCostLoading] = useState(false);
  const [monthlyCostLoading, setMonthlyCostLoading] = useState(false);
  const [sessionCostFailed, setSessionCostFailed] = useState(false);
  const [monthlyCostFailed, setMonthlyCostFailed] = useState(false);
  const sessionId = useRef<string | null>(null);
  const reading = useRef(false);
  const streamUnsubscribe = useRef<(() => void) | null>(null);
  const [host] = useState(() => injectedHost ?? createWebPresentationHost({ client, transport }));
  const settingsButtonRef = useRef<HTMLButtonElement>(null);
  const inspectButtonRef = useRef<HTMLButtonElement>(null);
  const { notify } = useToast();
  const { t, locale } = useTranslation();
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);

  function fail(error: unknown) {
    // Web-only auth status remains classified by the host; the UI owns only its safe outcome.
    if (host.isUnauthorized(error)) onUnauthorized?.();
    else setState(errored);
  }

  function readEvents(id: string) {
    if (reading.current) return;
    reading.current = true;
    streamUnsubscribe.current = host.subscribeProgress(
      id,
      (event) => setState((current) => reduce(current, event)),
      (error) => {
        reading.current = false;
        streamUnsubscribe.current = null;
        fail(error);
      },
      () => {
        reading.current = false;
        streamUnsubscribe.current = null;
      },
    );
  }

  async function ensureSession(): Promise<string> {
    if (sessionId.current) return sessionId.current;
    const model = selectedModel;
    const { session_id } = await host.openSession(model ?? undefined);
    sessionId.current = session_id;
    setSessionModel(model);
    setActiveId(session_id);
    void readEvents(session_id);
    return session_id;
  }

  async function refreshAgentControls(id = sessionId.current) {
    if (!id) {
      setAgentControls(null);
      setAgentControlsFailed(false);
      return;
    }
    setAgentControlsLoading(true);
    try {
      const projection = await host.getAgentControls(id);
      if (sessionId.current === id) {
        setAgentControls(projection);
        setAgentControlsFailed(false);
      }
    } catch {
      if (sessionId.current === id) {
        setAgentControls(null);
        setAgentControlsFailed(true);
      }
    } finally {
      if (sessionId.current === id) setAgentControlsLoading(false);
    }
  }

  async function refreshSessionCost(id = sessionId.current) {
    if (!id) {
      setSessionCost(null);
      setSessionCostFailed(false);
      return;
    }
    setSessionCostLoading(true);
    try {
      const cost = await host.getSessionCost(id);
      if (sessionId.current === id) {
        setSessionCost(cost);
        setSessionCostFailed(false);
      }
    } catch {
      if (sessionId.current === id) {
        setSessionCost(null);
        setSessionCostFailed(true);
      }
    } finally {
      if (sessionId.current === id) setSessionCostLoading(false);
    }
  }

  async function refreshMonthlyCost() {
    setMonthlyCostLoading(true);
    try {
      setMonthlyCost(await host.getMonthlyCost());
      setMonthlyCostFailed(false);
    } catch {
      setMonthlyCost(null);
      setMonthlyCostFailed(true);
    } finally {
      setMonthlyCostLoading(false);
    }
  }

  function refreshCosts(id = sessionId.current) {
    void refreshSessionCost(id);
    void refreshMonthlyCost();
  }

  async function send(prompt: string) {
    if (!prompt.trim()) return;
    const completedAttachments = attachments.filter(
      (item) => item.status === "done" && item.reference,
    );
    const uploads = completedAttachments.map((item) => ({
      reference: item.reference as string,
    }));
    const includesNonImage = completedAttachments.some(
      (item) => !item.mediaType?.startsWith("image/"),
    );

    setState((current) => userPrompt(current, prompt));
    try {
      const id = await ensureSession();
      if (includesNonImage) {
        const projection = await host.getAgentControls(id);
        if (sessionId.current === id) {
          setAgentControls(projection);
          setAgentControlsFailed(false);
        }
        if (!projection.actions.includes("attach_non_image_upload")) {
          throw new Error("upload reference unavailable");
        }
      }

      if (permissionModeDraft || uploads.length > 0) {
        await host.submit(id, prompt, {
          ...(permissionModeDraft
            ? { permissionMode: permissionModeDraft }
            : {}),
          ...(uploads.length > 0 ? { uploads } : {}),
        });
      } else {
        await host.submit(id, prompt);
      }
      setAttachments([]);
      setPermissionModeDraft(null);
      void refreshAgentControls(id);
      refreshCosts(id);
      void refreshSessions();
    } catch (error) {
      setComposerDraft(prompt);
      fail(error);
    }
  }

  function attachArtifactReference(reference: string) {
    setComposerDraft((current) =>
      current
        ? `${current}\n\n[artifact: ${reference}]`
        : `[artifact: ${reference}]`,
    );
    setComposerFocusToken((current) => current + 1);
  }

  // 031 — regenerate: re-run the last user turn through the existing send path.
  function regenerate() {
    for (let index = state.entries.length - 1; index >= 0; index--) {
      const entry = state.entries[index];
      if (entry.kind === "user") {
        void send(entry.text);
        return;
      }
    }
  }

  async function approve(requestId: string, decision: ApprovalDecision) {
    if (sessionId.current) {
      await host.answerApproval(sessionId.current, requestId, decision);
    }
    setState((current) => ({ ...current, pendingApproval: undefined }));
  }

  async function answer(requestId: string, answers: string[]) {
    if (sessionId.current) {
      await host.answerQuestion(sessionId.current, requestId, answers);
    }
    setState((current) => ({ ...current, pendingQuestion: undefined }));
  }

  async function stop() {
    if (!sessionId.current) return;
    try {
      await host.cancel(sessionId.current);
    } catch (error) {
      fail(error);
    }
  }

  function changeModel(model: string | null) {
    setSelectedModel(model);
    savePreferredModel(model);
  }

  async function refreshSessions() {
    try {
      setSessions(await host.listSessions());
    } catch {
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  }

  // 030 — session management: rename + delete, then refresh the list (with a 032 toast).
  async function renameSession(id: string, title: string) {
    try {
      await host.renameSession(id, title);
      notify(t("toast.renamed"));
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function deleteSession(id: string) {
    try {
      await host.deleteSession(id);
    } catch (error) {
      fail(error);
      return;
    }
    notify(t("toast.deleted"));
    // Deleting the open session returns the app to an empty/new state (FR-006).
    if (id === activeId || id === sessionId.current) newChat();
    void refreshSessions();
  }

  async function toggleStar(id: string, next: boolean) {
    try {
      await host.setSessionStarred(id, next);
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function searchSessions(query: string) {
    const trimmed = query.trim();
    try {
      setSessions(trimmed ? await host.searchSessions(trimmed) : await host.listSessions());
    } catch (error) {
      fail(error);
    }
  }

  async function bulkDeleteSessions(ids: string[]) {
    try {
      const result = await host.bulkDeleteSessions(ids);
      const deleted = new Set(result.deleted);
      if (activeId && deleted.has(activeId)) {
        const fallback = chooseActiveAfterDelete(activeId, sessions, deleted);
        if (fallback) void selectSession(fallback);
        else newChat();
      }
      notify(t("toast.deleted"));
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function forkFrom(sequence: number) {
    if (!sessionId.current) return;
    try {
      const forked = await host.forkSession(sessionId.current, { sequence });
      void refreshSessions();
      void selectSession(forked.session_id);
    } catch (error) {
      fail(error);
    }
  }

  // 032 — retry: clear the error and re-establish the live stream.
  function retry() {
    setState((current) => ({ ...current, status: "idle" }));
    if (sessionId.current) void readEvents(sessionId.current);
  }

  function newChat() {
    streamUnsubscribe.current?.();
    streamUnsubscribe.current = null;
    sessionId.current = null;
    reading.current = false;
    setActiveId(null);
    setSessionModel(null);
    setAgentControls(null);
    setAgentControlsFailed(false);
    setPermissionModeDraft(null);
    setSessionCost(null);
    setMonthlyCost(null);
    setSessionCostFailed(false);
    setMonthlyCostFailed(false);
    setState(initialState);
  }

  async function selectSession(id: string) {
    if (id === activeId) return;
    streamUnsubscribe.current?.();
    streamUnsubscribe.current = null;
    sessionId.current = id;
    setAgentControls(null);
    setAgentControlsFailed(false);
    setPermissionModeDraft(null);
    setSessionCost(null);
    setSessionCostFailed(false);
    setSessionModel(sessions.find((session) => session.session_id === id)?.model ?? null);
    reading.current = false;
    setActiveId(id);
    // Replay history through the same reducer, then stream live (R6).
    let next = initialState;
    setLoadingHistory(true);
    try {
      const events = (await host.history(id)) as RawEvent[];
      for (const event of events) next = reduce(next, event);
    } catch {
      next = initialState;
    } finally {
      setLoadingHistory(false);
    }
    setState(next);
    void refreshAgentControls(id);
    refreshCosts(id);
    void readEvents(id);
  }

  // Command-palette @-mentions: skill + tool names from the unit-027 inspection data (029).
  async function loadMentions(query: string): Promise<string[]> {
    try {
      const [skills, tools] = await Promise.all([
        host.inspectSkills(),
        host.inspectTools(),
      ]);
      const names = [...skills.skills.map((s) => s.name), ...tools.map((tool) => tool.name)];
      const needle = query.toLowerCase();
      return names.filter((name) => name.toLowerCase().includes(needle));
    } catch {
      return [];
    }
  }

  useEffect(() => {
    void refreshSessions();
    return () => host.teardown();
  }, [host]);

  const pendingApproval = state.pendingApproval;
  const pendingQuestion = state.pendingQuestion;
  const activeSession = sessions.find((session) => session.session_id === activeId);
  const activeModel = sessionModel ?? activeSession?.model ?? null;
  const attachmentUploading = attachments.some((item) => item.status === "uploading");
  const suggestionInput = useMemo(() => {
    const terminated = [...state.entries]
      .reverse()
      .find((entry) => entry.kind === "terminated");
    return {
      locale,
      sessionKey: activeId,
      permissionMode: permissionModeDraft,
      composerAvailable: state.status !== "running" && !showSettings,
      empty: state.entries.length === 0,
      settled: state.status === "terminated",
      terminalReason:
        terminated?.kind === "terminated" ? terminated.reason : null,
      contextLabel: activeSession?.context_name ?? null,
      attachments: attachments.map(({ name, status }) => ({ name, status })),
      tools: state.entries.flatMap((entry) =>
        entry.kind === "tool"
          ? [
              {
                outcome: entry.outcome,
                artifactReference: entry.artifactReference,
              },
            ]
          : [],
      ),
    };
  }, [
    activeId,
    activeSession?.context_name,
    attachments,
    locale,
    permissionModeDraft,
    showSettings,
    state.entries,
    state.status,
  ]);
  const suggestionsStaleKey = followUpSuggestionStaleKey(suggestionInput);
  useEffect(() => {
    setDismissedSuggestions([]);
  }, [suggestionsStaleKey]);
  const followUpSuggestions = deriveFollowUpSuggestions(suggestionInput)
    .filter((suggestion) => !dismissedSuggestions.includes(suggestion.id))
    .map((suggestion) => ({ ...suggestion, text: t(suggestion.textKey) }));

  return (
    <AppShell
      mobileSidebarOpen={mobileSidebarOpen}
      onDismissSidebar={() => setMobileSidebarOpen(false)}
      sidebar={
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onOpen={(id) => {
            setMobileSidebarOpen(false);
            void selectSession(id);
          }}
          onNew={() => {
            setMobileSidebarOpen(false);
            newChat();
          }}
          onRename={(id, title) => void renameSession(id, title)}
          onDelete={(id) => void deleteSession(id)}
          onToggleStar={(id, next) => void toggleStar(id, next)}
          onSearch={(query) => void searchSessions(query)}
          onBulkDelete={(ids) => void bulkDeleteSessions(ids)}
          loading={loadingSessions}
        />
      }
      header={
        <ChatHeader
          status={state.status}
          usage={state.usage}
          cost={sessionCostFailed ? null : sessionCost?.usd_spent ?? null}
          onStop={() => void stop()}
          inspectOpen={showInspect}
          onToggleInspect={() => setShowInspect((value) => !value)}
          settingsOpen={showSettings}
          onToggleSettings={() => {
            const next = !showSettings;
            setShowSettings(next);
            if (next) {
              void refreshAgentControls();
              refreshCosts();
            }
          }}
          settingsButtonRef={settingsButtonRef}
          inspectButtonRef={inspectButtonRef}
          contextName={activeSession?.context_name ?? undefined}
          modelName={activeModel}
          onToggleNavigation={() => setMobileSidebarOpen((open) => !open)}
          navigationOpen={mobileSidebarOpen}
        />
      }
      banner={state.status === "error" ? <ErrorBanner onRetry={retry} /> : undefined}
      panel={showInspect ? <InspectionPanel host={host} /> : undefined}
      onDismissPanel={() => setShowInspect(false)}
      panelReturnFocusRef={inspectButtonRef}
      composerHidden={showSettings}
      composer={
        <>
          <FollowUpSuggestions
            suggestions={followUpSuggestions}
            onSelect={(suggestion) => {
              setComposerDraft(suggestion.text);
              setDismissedSuggestions((current) => [...current, suggestion.id]);
              setComposerFocusToken((current) => current + 1);
            }}
            onDismiss={(id) =>
              setDismissedSuggestions((current) => [...current, id])
            }
          />
          <Composer
            disabled={state.status === "running"}
            sendDisabled={attachmentUploading}
            onSend={(text) => void send(text)}
            value={composerDraft}
            onValueChange={setComposerDraft}
            focusToken={composerFocusToken}
            commands={[{ id: "toggle-inspect", label: "Toggle inspection panel" }]}
            onCommand={(id) => {
              if (id === "toggle-inspect") setShowInspect((value) => !value);
            }}
            loadMentions={loadMentions}
            extras={
              <>
                <ModelSelector
                  client={host.webClient}
                  value={selectedModel}
                  onChange={changeModel}
                  scope={activeId ? "next" : "current"}
                />
                <Attachments client={host.webClient} value={attachments} onChange={setAttachments} />
              </>
            }
          />
        </>
      }
    >
      <div className="conversation-view" hidden={showSettings}>
        <MessageList
          entries={state.entries}
          onRegenerate={regenerate}
          canRegenerate={state.status !== "running"}
          onExample={(prompt) => void send(prompt)}
          onFork={(sequence) => void forkFrom(sequence)}
          onAttachReference={attachArtifactReference}
          loading={loadingHistory}
        />
      </div>
      {showSettings ? (
        <CapabilitySettingsView
          host={host}
          sessionId={sessionId.current}
          sessionOwned={Boolean(
            activeSession && activeSession.session_id === sessionId.current,
          )}
          sessionContext={
            activeSession?.session_id === sessionId.current ? activeSession : null
          }
          agentControls={agentControls}
          agentControlsLoading={agentControlsLoading}
          agentControlsFailed={agentControlsFailed}
          permissionModeDraft={permissionModeDraft}
          onPermissionModeChange={setPermissionModeDraft}
          onAgentControlsRefresh={() => {
            void refreshAgentControls();
            refreshCosts();
          }}
          sessionCost={sessionCost}
          monthlyCost={monthlyCost}
          sessionCostLoading={sessionCostLoading}
          monthlyCostLoading={monthlyCostLoading}
          sessionCostFailed={sessionCostFailed}
          monthlyCostFailed={monthlyCostFailed}
          onContextBound={refreshSessions}
          onBack={() => {
            setShowSettings(false);
            settingsButtonRef.current?.focus();
          }}
        />
      ) : null}
      {pendingApproval && (
        <ApprovalDialog
          toolName={pendingApproval.toolName}
          onDecide={(decision) => void approve(pendingApproval.requestId, decision)}
        />
      )}
      {pendingQuestion && (
        <QuestionDialog
          prompt={pendingQuestion.prompt}
          options={pendingQuestion.options}
          onAnswer={(answers) => void answer(pendingQuestion.requestId, answers)}
          onClose={() =>
            setState((current) => ({ ...current, pendingQuestion: undefined }))
          }
        />
      )}
    </AppShell>
  );
}
