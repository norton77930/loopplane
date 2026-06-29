import { useEffect, useRef, useState } from "react";

import {
  ApiClient,
  ApiError,
  createRestSessionTransport,
  type ApprovalDecision,
} from "./api/client";
import type { SessionTransport } from "./api/transport";
import type { RawEvent, SessionSummary } from "./api/types";
import { AppShell } from "./components/AppShell";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { Attachments, type Attachment } from "./components/Attachments";
import { ChatHeader } from "./components/ChatHeader";
import { Composer } from "./components/Composer";
import { ErrorBanner } from "./components/ErrorBanner";
import { InspectionPanel } from "./components/InspectionPanel";
import { MessageList } from "./components/MessageList";
import { ModelSelector } from "./components/ModelSelector";
import { QuestionDialog } from "./components/QuestionDialog";
import { Sidebar } from "./components/Sidebar";
import { useToast } from "./components/Toast";
import { useTranslation } from "./i18n/i18n";
import { estimateCost } from "./pricing";
import { errored, initialState, reduce, userPrompt } from "./state/chat";
import {
  chooseActiveAfterDelete,
  loadPreferredModel,
  savePreferredModel,
} from "./state/sessions";

export function App({
  client = new ApiClient(),
  transport: providedTransport,
  onUnauthorized,
}: {
  client?: ApiClient;
  transport?: SessionTransport;
  onUnauthorized?: () => void;
}) {
  const [state, setState] = useState(initialState);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showInspect, setShowInspect] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(() =>
    loadPreferredModel(),
  );
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const sessionId = useRef<string | null>(null);
  const reading = useRef(false);
  const { notify } = useToast();
  const { t } = useTranslation();
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [transport] = useState(
    () => providedTransport ?? createRestSessionTransport(client),
  );

  function fail(error: unknown) {
    // An authorization failure logs the user out (back to login); any other error shows the
    // non-blocking error banner (FR-010) while the conversation is preserved.
    if (error instanceof ApiError && error.status === 401) {
      onUnauthorized?.();
    } else {
      setState(errored);
    }
  }

  async function readEvents(id: string) {
    if (reading.current) return;
    reading.current = true;
    try {
      for await (const event of transport.streamSession(id)) {
        setState((current) => reduce(current, event));
      }
    } catch (error) {
      fail(error);
    } finally {
      reading.current = false;
    }
  }

  async function ensureSession(): Promise<string> {
    if (sessionId.current) return sessionId.current;
    const { session_id } = await transport.openSession(selectedModel ?? undefined);
    sessionId.current = session_id;
    setActiveId(session_id);
    void readEvents(session_id);
    return session_id;
  }

  async function send(prompt: string) {
    if (!prompt.trim()) return;
    const refs = attachments
      .filter((item) => item.status === "done" && item.reference)
      .map((item) => item.reference as string);
    const full = refs.length
      ? `${prompt}\n\n${refs.map((reference) => `[attachment: ${reference}]`).join("\n")}`
      : prompt;
    setState((current) => userPrompt(current, prompt));
    setAttachments([]);
    try {
      await transport.submit(await ensureSession(), full);
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
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
      await transport.answerApproval(sessionId.current, requestId, decision);
    }
    setState((current) => ({ ...current, pendingApproval: undefined }));
  }

  async function answer(requestId: string, answers: string[]) {
    if (sessionId.current) {
      await transport.answerQuestion(sessionId.current, requestId, answers);
    }
    setState((current) => ({ ...current, pendingQuestion: undefined }));
  }

  async function stop() {
    if (!sessionId.current) return;
    try {
      await transport.cancel(sessionId.current);
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
      setSessions(await client.listSessions());
    } catch {
      setSessions([]);
    } finally {
      setLoadingSessions(false);
    }
  }

  // 030 — session management: rename + delete, then refresh the list (with a 032 toast).
  async function renameSession(id: string, title: string) {
    try {
      await client.renameSession(id, title);
      notify(t("toast.renamed"));
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function deleteSession(id: string) {
    try {
      await client.deleteSession(id);
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
      if (next) await client.starSession(id);
      else await client.unstarSession(id);
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function searchSessions(query: string) {
    const trimmed = query.trim();
    try {
      setSessions(trimmed ? await client.searchSessions(trimmed) : await client.listSessions());
    } catch (error) {
      fail(error);
    }
  }

  async function bulkDeleteSessions(ids: string[]) {
    try {
      const result = await client.bulkDeleteSessions(ids);
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
      const forked = await client.forkSession(sessionId.current, { sequence });
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
    sessionId.current = null;
    reading.current = false;
    setActiveId(null);
    setState(initialState);
  }

  async function selectSession(id: string) {
    if (id === activeId) return;
    sessionId.current = id;
    reading.current = false;
    setActiveId(id);
    // Replay history through the same reducer, then stream live (R6).
    let next = initialState;
    setLoadingHistory(true);
    try {
      const events = (await client.history(id)) as RawEvent[];
      for (const event of events) next = reduce(next, event);
    } catch {
      next = initialState;
    } finally {
      setLoadingHistory(false);
    }
    setState(next);
    void readEvents(id);
  }

  // Command-palette @-mentions: skill + tool names from the unit-027 inspection data (029).
  async function loadMentions(query: string): Promise<string[]> {
    try {
      const [skills, tools] = await Promise.all([
        client.inspectSkills(),
        client.inspectTools(),
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
  }, []);

  const pendingApproval = state.pendingApproval;
  const pendingQuestion = state.pendingQuestion;
  const activeSession = sessions.find((session) => session.session_id === activeId);

  return (
    <AppShell
      sidebar={
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onOpen={(id) => void selectSession(id)}
          onNew={newChat}
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
          cost={estimateCost(state.usage.total, selectedModel)}
          onStop={() => void stop()}
          inspectOpen={showInspect}
          onToggleInspect={() => setShowInspect((value) => !value)}
          contextName={activeSession?.context_name ?? undefined}
        />
      }
      banner={state.status === "error" ? <ErrorBanner onRetry={retry} /> : undefined}
      panel={showInspect ? <InspectionPanel client={client} /> : undefined}
      composer={
        <Composer
          disabled={state.status === "running"}
          onSend={(text) => void send(text)}
          commands={[{ id: "toggle-inspect", label: "Toggle inspection panel" }]}
          onCommand={(id) => {
            if (id === "toggle-inspect") setShowInspect((value) => !value);
          }}
          loadMentions={loadMentions}
          extras={
            <>
              <ModelSelector
                client={client}
                value={selectedModel}
                onChange={changeModel}
              />
              <Attachments client={client} onChange={setAttachments} />
            </>
          }
        />
      }
    >
      <MessageList
        entries={state.entries}
        onRegenerate={regenerate}
        canRegenerate={state.status !== "running"}
        onExample={(prompt) => void send(prompt)}
        onFork={(sequence) => void forkFrom(sequence)}
        loading={loadingHistory}
      />
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
