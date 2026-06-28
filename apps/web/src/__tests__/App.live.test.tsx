import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { SessionTransport } from "../api/transport";
import type { RawEvent } from "../api/types";
import { App } from "../App";

function makeClient(): ApiClient {
  return {
    listSessions: async () => [],
    listModels: async () => [],
    uploadFile: async () => ({ reference: "r", name: "f" }),
    inspectSkills: async () => ({ skills: [], problems: [] }),
    inspectTools: async () => [],
  } as unknown as ApiClient;
}

function makeTransport(overrides: Partial<SessionTransport> = {}): SessionTransport {
  return {
    mode: "live",
    openSession: async () => ({ session_id: "live-1" }),
    streamSession: async function* (): AsyncGenerator<RawEvent> {
      yield { type: "assistant-output-increment", payload: { text: "live", turn_index: 0 } };
      yield { type: "run-terminated", payload: { reason: "done", turns_taken: 1 } };
    },
    submit: async () => undefined,
    answerApproval: async () => undefined,
    answerQuestion: async () => undefined,
    cancel: async () => undefined,
    ...overrides,
  };
}

describe("App live transport", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("uses an injected live transport for session submit and stream", async () => {
    const submit = vi.fn().mockResolvedValue(undefined);
    render(<App client={makeClient()} transport={makeTransport({ submit })} />);

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("live-1", "hello"));
    await waitFor(() => expect(screen.getByText("live")).toBeInTheDocument());
  });
});
