import { useState } from "react";

import { Conversation } from "@web/components/Conversation";
import { Prompts } from "@web/components/Prompts";
import { Timeline } from "@web/components/Timeline";
import { errored, initialState, reduce, userPrompt } from "@web/state/chat";

import type { SidecarTransport } from "./sidecar";

export function App({ transport }: { transport: SidecarTransport }) {
  const [state, setState] = useState(initialState);
  const [input, setInput] = useState("");

  async function send(prompt: string) {
    if (!prompt.trim()) return;
    setState((current) => userPrompt(current, prompt));
    try {
      for await (const event of transport.run(prompt)) {
        setState((current) => reduce(current, event));
      }
    } catch {
      setState(errored);
    }
  }

  return (
    <main className="app">
      <h1>LoopPlane Desktop</h1>
      {state.status === "error" && (
        <div className="error" role="alert">
          Disconnected — please retry.
        </div>
      )}
      <Conversation turns={state.turns} />
      <Timeline entries={state.timeline} />
      <Prompts
        state={state}
        onApproval={(id, allow) => transport.answerApproval(id, allow)}
        onQuestion={(id, text) => transport.answerQuestion(id, [text])}
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
    </main>
  );
}
