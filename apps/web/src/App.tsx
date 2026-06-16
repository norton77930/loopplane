import { useRef, useState } from "react";

import { ApiClient, ApiError } from "./api/client";
import type { SessionSummary } from "./api/types";
import { Conversation } from "./components/Conversation";
import { Prompts } from "./components/Prompts";
import { SessionList } from "./components/SessionList";
import { Timeline } from "./components/Timeline";
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
  const [input, setInput] = useState("");
  const sessionId = useRef<string | null>(null);
  const reading = useRef(false);

  function fail(error: unknown) {
    // An authorization failure logs the user out (back to login); any other
    // error shows the existing disconnected state (unit-018 behavior).
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
    }
  }

  async function ensureSession(): Promise<string> {
    if (sessionId.current) return sessionId.current;
    const { session_id } = await client.openSession();
    sessionId.current = session_id;
    void readEvents(session_id);
    return session_id;
  }

  async function send(prompt: string) {
    if (!prompt.trim()) return;
    setState((current) => userPrompt(current, prompt));
    try {
      await client.submit(await ensureSession(), prompt);
    } catch (error) {
      fail(error);
    }
  }

  async function approve(requestId: string, allow: boolean) {
    if (sessionId.current) {
      await client.answerApproval(sessionId.current, requestId, { allow });
    }
    setState((current) => ({ ...current, pendingApproval: undefined }));
  }

  async function answer(requestId: string, text: string) {
    if (sessionId.current) {
      await client.answerQuestion(sessionId.current, requestId, [text]);
    }
    setState((current) => ({ ...current, pendingQuestion: undefined }));
  }

  async function refreshSessions() {
    try {
      setSessions(await client.listSessions());
    } catch {
      setSessions([]);
    }
  }

  return (
    <main className="app">
      <h1>LoopPlane</h1>
      {state.status === "error" && (
        <div className="error" role="alert">
          Disconnected — please retry.
        </div>
      )}
      <Conversation turns={state.turns} />
      <Timeline entries={state.timeline} />
      <Prompts
        state={state}
        onApproval={(id, allow) => void approve(id, allow)}
        onQuestion={(id, text) => void answer(id, text)}
      />
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          void send(input);
          setInput("");
        }}
      >
        <input
          aria-label="prompt"
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />
        <button type="submit">Send</button>
      </form>
      <button type="button" onClick={() => void refreshSessions()}>
        Sessions
      </button>
      <SessionList sessions={sessions} onOpen={() => undefined} />
    </main>
  );
}
