import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { SessionTransport } from "../api/transport";
import type { RawEvent } from "../api/types";
import { App } from "../App";
import { WebPresentationHost } from "../presentation-host";

function makeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    listSessions: async () => [],
    listModels: async () => [],
    uploadFile: async () => ({ reference: "r", name: "f" }),
    ...overrides,
  } as unknown as ApiClient;
}

function makeTransport(
  events: RawEvent[],
  overrides: Partial<SessionTransport> = {},
): SessionTransport {
  return {
    mode: "rest_sse",
    openSession: async () => ({ session_id: "web-1" }),
    streamSession: async function* () {
      for (const event of events) yield event;
    },
    submit: async () => undefined,
    answerApproval: async () => undefined,
    answerQuestion: async () => undefined,
    cancel: async () => undefined,
    ...overrides,
  };
}

describe("WebPresentationHost (T063)", () => {
  it("projects sessions and preserves host-owned Web delegation results", async () => {
    const client = makeClient({
      listSessions: vi.fn().mockResolvedValue([
        { session_id: "saved-1", label: "Saved", starred: true, last_active_at: "2026-08-09T00:00:00Z", created_at: "2026-08-09T00:00:00Z" },
      ]),
      inspectSkills: vi.fn().mockResolvedValue({ skills: [], problems: [] }),
      inspectTools: vi.fn().mockResolvedValue([]),
      getAgentControls: vi.fn().mockResolvedValue({ session_id: "saved-1" }),
      getCapabilitySettings: vi.fn().mockResolvedValue({ mutations_enabled: false }),
      getSessionCost: vi.fn().mockResolvedValue({ usd_spent: "1.00" }),
      getMonthlyCost: vi.fn().mockResolvedValue({ usd_spent: "2.00" }),
      uploadFile: vi.fn().mockResolvedValue({ reference: "upload-1", name: "note.txt" }),
    });
    const host = new WebPresentationHost({ client });
    const file = new File(["note"], "note.txt");

    await expect(host.listSessionProjections()).resolves.toEqual([
      { id: "saved-1", title: "Saved", starred: true, projectId: null },
    ]);
    await expect(host.inspectSkills()).resolves.toEqual({ skills: [], problems: [] });
    await expect(host.inspectTools()).resolves.toEqual([]);
    await expect(host.getAgentControls("saved-1")).resolves.toEqual({ session_id: "saved-1" });
    await expect(host.getCapabilitySettings()).resolves.toEqual({ mutations_enabled: false });
    await expect(host.getSessionCost("saved-1")).resolves.toEqual({ usd_spent: "1.00" });
    await expect(host.getMonthlyCost()).resolves.toEqual({ usd_spent: "2.00" });
    await expect(host.uploadFile(file)).resolves.toEqual({ reference: "upload-1", name: "note.txt" });
    expect(client.uploadFile).toHaveBeenCalledWith(file);
  });

  it("owns stream subscription teardown and never forwards events after unsubscribe", async () => {
    let releaseSecond!: () => void;
    const second = new Promise<void>((resolve) => { releaseSecond = resolve; });
    const transport = makeTransport([], {
      streamSession: async function* () {
        yield { type: "assistant-output-increment", payload: { text: "first" } };
        await second;
        yield { type: "assistant-output-increment", payload: { text: "second" } };
      },
    });
    const received: string[] = [];
    const host = new WebPresentationHost({ client: makeClient(), transport });
    const unsubscribe = host.subscribeProgress("web-1", (event) => received.push(event.type));

    await waitFor(() => expect(received).toEqual(["assistant-output-increment"]));
    unsubscribe();
    releaseSecond();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(received).toEqual(["assistant-output-increment"]);
    host.teardown();
  });

  it("delegates submit options, exact interaction identities, cancellation, and error identity", async () => {
    const failure = new Error("transport unavailable");
    const submit = vi.fn().mockRejectedValue(failure);
    const answerApproval = vi.fn().mockResolvedValue(undefined);
    const answerQuestion = vi.fn().mockResolvedValue(undefined);
    const cancel = vi.fn().mockResolvedValue(undefined);
    const host = new WebPresentationHost({
      client: makeClient(),
      transport: makeTransport([], { submit, answerApproval, answerQuestion, cancel }),
    });
    const options = { permissionMode: "plan", uploads: [{ reference: "upload-1" }] };

    await expect(host.submit("web-1", "prompt", options)).rejects.toBe(failure);
    expect(submit).toHaveBeenCalledWith("web-1", "prompt", options);
    await host.answerApproval("web-1", "approval-1", { allow: true, scope: "session" });
    await host.answerQuestion("web-1", "question-1", ["A"]);
    await host.cancel("web-1");
    expect(answerApproval).toHaveBeenCalledWith("web-1", "approval-1", { allow: true, scope: "session" });
    expect(answerQuestion).toHaveBeenCalledWith("web-1", "question-1", ["A"]);
    expect(cancel).toHaveBeenCalledWith("web-1");
  });
});

describe("Web presentation-host baseline equivalence (T058)", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("preserves session listing, submit, and normalized progress through injected Web transports", async () => {
    const listSessions = vi.fn().mockResolvedValue([
      {
        session_id: "saved-1",
        label: "Saved",
        last_active_at: "2026-08-09T00:00:00Z",
        created_at: "2026-08-09T00:00:00Z",
        starred: false,
      },
    ]);
    const openSession = vi.fn().mockResolvedValue({ session_id: "web-1" });
    const submit = vi.fn().mockResolvedValue(undefined);
    const transport = makeTransport(
      [
        {
          type: "assistant-output-increment",
          payload: { text: "transport output", turn_index: 0 },
        },
        {
          type: "run-terminated",
          payload: { reason: "natural-completion", turns_taken: 1 },
        },
      ],
      { openSession, submit },
    );

    render(<App client={makeClient({ listSessions })} transport={transport} />);

    await waitFor(() => expect(listSessions).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(openSession).toHaveBeenCalledWith(undefined));
    await waitFor(() => expect(submit).toHaveBeenCalledWith("web-1", "hello"));
    expect(await screen.findByText("transport output")).toBeInTheDocument();
  });

  it("preserves approval and question identities at the transport boundary", async () => {
    const answerApproval = vi.fn().mockResolvedValue(undefined);
    const approvalTransport = makeTransport(
      [
        {
          type: "approval-requested",
          payload: { request_id: "approval-1", tool_name: "shell", input_summary: "safe" },
        },
      ],
      { answerApproval },
    );
    const approvalView = render(
      <App client={makeClient()} transport={approvalTransport} />,
    );

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "approve" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const approval = await screen.findByTestId("approval");
    fireEvent.click(within(approval).getByText("Always allow this session"));
    await waitFor(() =>
      expect(answerApproval).toHaveBeenCalledWith("web-1", "approval-1", {
        allow: true,
        scope: "session",
      }),
    );
    approvalView.unmount();

    const answerQuestion = vi.fn().mockResolvedValue(undefined);
    const questionTransport = makeTransport(
      [
        {
          type: "question-asked",
          payload: {
            request_id: "question-1",
            questions: [{ text: "Pick", options: ["A", "B"] }],
          },
        },
      ],
      { answerQuestion },
    );
    render(<App client={makeClient()} transport={questionTransport} />);

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "answer" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const question = await screen.findByTestId("question");
    fireEvent.click(within(question).getByRole("checkbox", { name: "B" }));
    fireEvent.click(within(question).getByText("Send"));
    await waitFor(() =>
      expect(answerQuestion).toHaveBeenCalledWith("web-1", "question-1", ["B"]),
    );
  });

  it("preserves cancellation identity without exposing transport details to the UI", async () => {
    const cancel = vi.fn().mockResolvedValue(undefined);
    const transport = makeTransport(
      [
        {
          type: "assistant-output-increment",
          payload: { text: "working", turn_index: 0 },
        },
      ],
      { cancel },
    );

    render(<App client={makeClient()} transport={transport} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "run" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(await screen.findByText("Stop"));

    await waitFor(() => expect(cancel).toHaveBeenCalledWith("web-1"));
    expect(document.body.textContent).not.toMatch(/request[_-]?id|mutation[_-]?id/i);
  });
});
