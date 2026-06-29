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
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
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
