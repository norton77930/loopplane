import { useState } from "react";

import { ApprovalDialog } from "@web/components/ApprovalDialog";
import { MessageList } from "@web/components/MessageList";
import { QuestionDialog } from "@web/components/QuestionDialog";
import { errored, initialState, reduce, userPrompt } from "@web/state/chat";
import type { RawEvent } from "@web/api/types";

import type { SidecarTransport } from "./sidecar";

export function App({ transport }: { transport: SidecarTransport }) {
  const [state, setState] = useState(initialState);
  const [input, setInput] = useState("");
  const pendingApproval = state.pendingApproval;
  const pendingQuestion = state.pendingQuestion;

  async function send(prompt: string) {
    if (!prompt.trim()) return;
    setState((current) => userPrompt(current, prompt));
    try {
      for await (const event of transport.run(prompt)) {
        applyEvent(event);
      }
    } catch {
      setState(errored);
    }
  }

  function applyEvent(event: RawEvent) {
    setState((current) => reduce(current, event));
  }

  return (
    <main className="app">
      <h1>LoopPlane Desktop</h1>
      {state.status === "error" && (
        <div className="error" role="alert">
          Disconnected — please retry.
        </div>
      )}
      <MessageList entries={state.entries} loading={state.status === "running"} />
      {pendingApproval && (
        <ApprovalDialog
          toolName={pendingApproval.toolName}
          onDecide={(decision) => {
            transport.answerApproval(pendingApproval.requestId, decision.allow);
            setState((current) => ({ ...current, pendingApproval: undefined }));
          }}
        />
      )}
      {pendingQuestion && (
        <QuestionDialog
          prompt={pendingQuestion.prompt}
          options={pendingQuestion.options}
          onAnswer={(answers) => {
            transport.answerQuestion(pendingQuestion.requestId, answers);
            setState((current) => ({ ...current, pendingQuestion: undefined }));
          }}
          onClose={() =>
            setState((current) => ({ ...current, pendingQuestion: undefined }))
          }
        />
      )}
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
    </main>
  );
}
