import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { RawEvent } from "../api/types";
import { App } from "../App";

function makeClient(overrides: Record<string, unknown> = {}): ApiClient {
  return {
    openSession: async () => ({ session_id: "s1" }),
    streamSession: async function* () {
      /* no events by default */
    },
    submit: async () => ({}),
    listSessions: async () => [],
    answerApproval: async () => undefined,
    answerQuestion: async () => undefined,
    cancel: async () => undefined,
    history: async () => [],
    ...overrides,
  } as unknown as ApiClient;
}

function streamingClient(events: RawEvent[], overrides: Record<string, unknown> = {}): ApiClient {
  return makeClient({
    streamSession: async function* () {
      for (const event of events) yield event;
    },
    ...overrides,
  });
}

describe("App", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("streams a run and renders the conversation as markdown", async () => {
    const client = streamingClient([
      { type: "assistant-output-increment", payload: { text: "hi there", turn_index: 0 } },
      { type: "run-terminated", payload: { reason: "natural-completion", turns_taken: 1 } },
    ]);
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText(/natural-completion/)).toBeInTheDocument();
  });

  it("shows a non-blocking error banner when the stream fails", async () => {
    const client = makeClient({
      // eslint-disable-next-line require-yield
      streamSession: async function* (): AsyncGenerator<RawEvent> {
        throw new Error("dropped");
      },
    });
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("renders an approval dialog and forwards the session-scoped decision", async () => {
    const answerApproval = vi.fn().mockResolvedValue(undefined);
    const client = streamingClient(
      [{ type: "approval-requested", payload: { request_id: "r1", tool_name: "danger", input_summary: "x" } }],
      { answerApproval },
    );
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "go" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const dialog = await screen.findByTestId("approval");
    fireEvent.click(within(dialog).getByText("Always allow this session"));
    await waitFor(() =>
      expect(answerApproval).toHaveBeenCalledWith("s1", "r1", { allow: true, scope: "session" }),
    );
  });

  it("cancels an in-flight run via the Stop control", async () => {
    const cancel = vi.fn().mockResolvedValue(undefined);
    const client = streamingClient(
      [{ type: "assistant-output-increment", payload: { text: "working", turn_index: 0 } }],
      { cancel },
    );
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "go" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const stop = await screen.findByText("Stop");
    fireEvent.click(stop);
    await waitFor(() => expect(cancel).toHaveBeenCalledWith("s1"));
  });
});
