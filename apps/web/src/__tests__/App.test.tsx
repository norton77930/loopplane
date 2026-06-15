import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { RawEvent } from "../api/types";
import { App } from "../App";

function streamingClient(events: RawEvent[]): ApiClient {
  return {
    openSession: async () => ({ session_id: "s1" }),
    streamSession: async function* () {
      for (const event of events) yield event;
    },
    submit: async () => ({}),
    listSessions: async () => [],
    answerApproval: async () => undefined,
    answerQuestion: async () => undefined,
  } as unknown as ApiClient;
}

describe("App", () => {
  it("streams a run and renders the conversation", async () => {
    const client = streamingClient([
      { type: "assistant-output-increment", payload: { text: "hi there", turn_index: 0 } },
      { type: "run-terminated", payload: { reason: "natural-completion", turns_taken: 1 } },
    ]);
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("shows a clear error state when the stream fails", async () => {
    const client = {
      openSession: async () => ({ session_id: "s1" }),
      // eslint-disable-next-line require-yield
      streamSession: async function* (): AsyncGenerator<RawEvent> {
        throw new Error("dropped");
      },
      submit: async () => ({}),
      listSessions: async () => [],
    } as unknown as ApiClient;
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hi" } });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
