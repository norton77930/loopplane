import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { SessionSummary } from "../api/types";
import { App } from "../App";

const session = (over: Partial<SessionSummary> = {}): SessionSummary => ({
  session_id: "s1",
  label: "Alpha",
  last_active_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  starred: false,
  ...over,
});

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
    listModels: async () => [],
    uploadFile: async () => ({ reference: "r", name: "f" }),
    starSession: async () => undefined,
    unstarSession: async () => undefined,
    searchSessions: async () => [],
    forkSession: async () => ({ session_id: "fork" }),
    bulkDeleteSessions: async () => ({ deleted: [] }),
    ...overrides,
  } as unknown as ApiClient;
}

describe("App session parity wiring", () => {
  beforeEach(() => {
    localStorage.clear();
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("keeps the active session model distinct from the next-chat preference", async () => {
    localStorage.setItem("loopplane.preferredModel", "gpt-4o-mini");
    const openSession = vi.fn().mockResolvedValue({ session_id: "new-session" });
    const client = makeClient({
      openSession,
      listSessions: async () => [
        session({ session_id: "s1", label: "Alpha", model: "claude-opus" }),
      ],
      listModels: async () => [
        { id: "gpt-4o-mini", label: "GPT-4o mini" },
        { id: "gpt-4o", label: "GPT-4o" },
        { id: "claude-opus", label: "Claude Opus" },
      ],
      history: async () => [
        {
          type: "turn-completed",
          payload: {
            turn_index: 0,
            stop_reason: "end-turn",
            usage: {
              input_tokens: 1_000_000,
              output_tokens: 1_000_000,
              cached_tokens: 0,
              reasoning_tokens: 0,
            },
          },
        },
      ],
    });

    render(<App client={client} />);
    fireEvent.click(await screen.findByText("Alpha"));

    expect(await screen.findByText("Active model: claude-opus")).toBeInTheDocument();
    expect(await screen.findByLabelText("Next chat model")).toHaveValue("gpt-4o-mini");
    expect(await screen.findByTestId("usage")).not.toHaveTextContent("$");

    fireEvent.change(screen.getByLabelText("Next chat model"), {
      target: { value: "gpt-4o" },
    });
    expect(screen.getByText("Active model: claude-opus")).toBeInTheDocument();
    expect(screen.getByTestId("usage")).not.toHaveTextContent("$");

    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(openSession).toHaveBeenCalledWith("gpt-4o"));
  });

  it("wires sidebar star, search, and bulk delete actions", async () => {
    const starSession = vi.fn().mockResolvedValue(undefined);
    const searchSessions = vi
      .fn()
      .mockResolvedValue([session({ session_id: "s2", label: "Beta" })]);
    const bulkDeleteSessions = vi.fn().mockResolvedValue({ deleted: ["s1"] });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = makeClient({
      listSessions: async () => [session(), session({ session_id: "s2", label: "Beta" })],
      starSession,
      searchSessions,
      bulkDeleteSessions,
    });

    render(<App client={client} />);

    await screen.findByText("Alpha");
    fireEvent.click(screen.getByRole("button", { name: "star session Alpha" }));
    await waitFor(() => expect(starSession).toHaveBeenCalledWith("s1"));

    fireEvent.click(screen.getByLabelText("select Alpha"));
    fireEvent.click(screen.getByRole("button", { name: "Delete selected" }));
    await waitFor(() => expect(bulkDeleteSessions).toHaveBeenCalledWith(["s1"]));

    fireEvent.change(screen.getByLabelText("search sessions"), {
      target: { value: "alpha" },
    });
    await waitFor(() => expect(searchSessions).toHaveBeenCalledWith("alpha"));

    confirm.mockRestore();
  });

  it("wires message fork to the active session", async () => {
    const forkSession = vi.fn().mockResolvedValue({ session_id: "fork" });
    const client = makeClient({ forkSession });

    render(<App client={client} />);

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(await screen.findByText("Fork"));

    await waitFor(() =>
      expect(forkSession).toHaveBeenCalledWith("s1", { sequence: 1 }),
    );
  });
});
