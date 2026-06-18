import { useEffect, useRef, useState } from "react";

import { ApiClient, ApiError, type ApprovalDecision } from "./api/client";
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
import { errored, initialState, reduce, userPrompt } from "./state/chat";

export function App({
  client = new ApiClient(),
  onUnauthorized,
}: {
  client?: ApiClient;
  onUnauthorized?: () => void;
}) {
  const [state, setState] = useState(initialState);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showInspect, setShowInspect] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const sessionId = useRef<string | null>(null);
  const reading = useRef(false);

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
      for await (const event of client.streamSession(id)) {
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
    const { session_id } = await client.openSession(selectedModel ?? undefined);
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
      await client.submit(await ensureSession(), full);
      void refreshSessions();
    } catch (error) {
      fail(error);
    }
  }

  async function approve(requestId: string, decision: ApprovalDecision) {
    if (sessionId.current) {
      await client.answerApproval(sessionId.current, requestId, decision);
    }
    setState((current) => ({ ...current, pendingApproval: undefined }));
  }

  async function answer(requestId: string, answers: string[]) {
    if (sessionId.current) {
      await client.answerQuestion(sessionId.current, requestId, answers);
    }
    setState((current) => ({ ...current, pendingQuestion: undefined }));
  }

  async function stop() {
    if (!sessionId.current) return;
    try {
      await client.cancel(sessionId.current);
    } catch (error) {
      fail(error);
    }
  }

  async function refreshSessions() {
    try {
      setSessions(await client.listSessions());
    } catch {
      setSessions([]);
    }
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
    try {
      const events = (await client.history(id)) as RawEvent[];
      for (const event of events) next = reduce(next, event);
    } catch {
      next = initialState;
    }
    setState(next);
    void readEvents(id);
  }

  useEffect(() => {
    void refreshSessions();
  }, []);

  const pendingApproval = state.pendingApproval;
  const pendingQuestion = state.pendingQuestion;

  return (
    <AppShell
      sidebar={
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onOpen={(id) => void selectSession(id)}
          onNew={newChat}
        />
      }
      header={
        <ChatHeader
          status={state.status}
          usage={state.usage}
          onStop={() => void stop()}
          inspectOpen={showInspect}
          onToggleInspect={() => setShowInspect((value) => !value)}
        />
      }
      banner={state.status === "error" ? <ErrorBanner /> : undefined}
      panel={showInspect ? <InspectionPanel client={client} /> : undefined}
      composer={
        <Composer
          disabled={state.status === "running"}
          onSend={(text) => void send(text)}
          extras={
            <>
              <ModelSelector
                client={client}
                value={selectedModel}
                onChange={setSelectedModel}
              />
              <Attachments client={client} onChange={setAttachments} />
            </>
          }
        />
      }
    >
      <MessageList entries={state.entries} />
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
        />
      )}
    </AppShell>
  );
}
