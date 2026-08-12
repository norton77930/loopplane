import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { generatedCapabilityFixtures, generatedSessionEventFixtures } from "@web/api/generated";
import type {
  ManagedSchedule,
  McpConfiguration,
  ModelDefault,
  RawEvent,
  WorkspaceContext,
} from "@web/api/types";

import { App } from "../App";
import type { SidecarTransport } from "../sidecar";

function stubTransport(
  events: RawEvent[],
  overrides: Partial<
    Pick<
      SidecarTransport,
      "answerApproval" | "answerQuestion" | "cancel" | "status" | "dispose"
    >
  > = {},
): SidecarTransport {
  return {
    run: async function* () {
      for (const event of events) yield event;
    },
    answerApproval: () => undefined,
    answerQuestion: () => undefined,
    cancel: () => undefined,
    status: async () => ({ ready: true }),
    dispose: async () => undefined,
    listSessions: async () => [],
    listProjects: async () => [],
    listWorkspaces: async () => [],
    setDraft: () => undefined,
    clearDraft: () => undefined,
    activeSessionId: null,
    activeSubscriptionId: null,
    ...overrides,
  } as unknown as SidecarTransport;
}

describe("App (desktop single-session composition, T031)", () => {
  it("preserves the shared approval-dialog decision contract", async () => {
    const answerApproval = vi.fn();
    const transport = stubTransport(
      [
        {
          type: "approval-requested",
          payload: { request_id: "approval-1", tool_name: "danger", input_summary: "x" },
        },
      ],
      { answerApproval },
    );

    render(<App transport={transport} />);
    fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "run it" } });
    fireEvent.click(screen.getByText("Send"));
    fireEvent.click(await screen.findByText("Allow"));

    expect(answerApproval).toHaveBeenCalledWith("approval-1", true);
  });

  it("preserves the shared question-dialog answer contract", async () => {
    const answerQuestion = vi.fn();
    const transport = stubTransport(
      [
        {
          type: "question-asked",
          payload: {
            request_id: "question-1",
            questions: [{ text: "Pick one", options: ["A", "B"] }],
          },
        },
      ],
      { answerQuestion },
    );

    render(<App transport={transport} />);
    fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "ask" } });
    fireEvent.click(screen.getByText("Send"));
    fireEvent.click(await screen.findByRole("checkbox", { name: "A" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Send"));

    expect(answerQuestion).toHaveBeenCalledWith("question-1", ["A"]);
  });

  it("renders a streamed run over the sidecar transport", async () => {
    const transport = stubTransport([
      { type: "assistant-output-increment", payload: { text: "hi there", turn_index: 0 } },
      { type: "run-terminated", payload: { reason: "natural-completion", turns_taken: 1 } },
    ]);
    render(<App transport={transport} />);
    fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
    expect(screen.getByText("hello")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("runtime-status").textContent).toMatch(/Outcome|finished/i),
    );
  });

  it("exposes cancel during a run", async () => {
    const cancel = vi.fn();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const transport = {
      run: async function* () {
        yield {
          type: "assistant-output-increment",
          payload: { text: "partial", turn_index: 0 },
        } as RawEvent;
        await gate;
      },
      answerApproval: () => undefined,
      answerQuestion: () => undefined,
      cancel,
      status: async () => ({ ready: true }),
      dispose: async () => undefined,
    } as unknown as SidecarTransport;

    render(<App transport={transport} />);
    fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "go" } });
    fireEvent.click(screen.getByText("Send"));
    await screen.findByText("partial");
    fireEvent.click(screen.getByLabelText("cancel run"));
    expect(cancel).toHaveBeenCalled();
    release();
  });

  it("keeps one-run permission selection as a draft until the local host accepts submit", async () => {
    const previousApi = window.loopplaneDesktop;
    const getAgentControls = vi.fn().mockResolvedValue({
      default_mode: null,
      selectable_modes: [{ id: "plan", kind: "plan", summary: "" }],
      active_run: { mode: "ask", state: "active", planActive: false },
      last_accepted_run: { mode: "ask", state: "settled", planActive: false },
      budget: { tracking: "unavailable", pricing: "unpriced" },
      actions: ["select_permission_mode"],
      unavailable: false,
    });
    window.loopplaneDesktop = {
      inspection: { get: vi.fn().mockResolvedValue({ skills: [], tools: [], mcp: [], memory: [] }) },
      agentControls: { get: getAgentControls },
      capabilities: { list: vi.fn().mockResolvedValue({ capabilities: [] }), invokeAction: vi.fn() },
    } as never;
    const runs: Array<{ prompt: string; options: unknown }> = [];
    const transport = {
      ...stubTransport([]),
      activeSessionId: "session-1",
      run: async function* (prompt: string, options: unknown) {
        runs.push({ prompt, options });
        yield { type: "run-terminated", payload: { reason: "natural-completion", turns_taken: 1 } } as RawEvent;
      },
    } as unknown as SidecarTransport;

    try {
      render(<App transport={transport} resumeSessionId="session-1" />);
      await waitFor(() => {
        expect(getAgentControls).toHaveBeenCalledWith("session-1");
        expect(screen.getByText("Budget pricing: unpriced")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole("button", { name: "Settings" }));
      const agentControlsTab = screen.getByRole("tab", { name: "Agent controls" });
      fireEvent.click(agentControlsTab);
      await waitFor(() => expect(agentControlsTab).toHaveAttribute("aria-selected", "true"));
      await screen.findByText("Active run");
      const select = await screen.findByLabelText("Permission mode for next run");
      fireEvent.change(select, { target: { value: "plan" } });

      expect(screen.getByText(/Draft for next run/)).toHaveTextContent("plan");
      expect(screen.getByText("Active run").nextSibling).toHaveTextContent("ask");
      expect(screen.getByText("Last accepted run").nextSibling).toHaveTextContent("ask");

      fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
      fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "second" } });
      fireEvent.click(screen.getByText("Send"));
      await waitFor(() => expect(runs).toHaveLength(1));
      expect(runs[0]).toEqual({ prompt: "second", options: { workspaceId: undefined, permissionMode: "plan" } });

      fireEvent.click(screen.getByRole("button", { name: "Settings" }));
      fireEvent.click(screen.getByRole("tab", { name: "Agent controls" }));
      await waitFor(() => expect(screen.queryByText(/Draft for next run/)).toBeNull());
    } finally {
      window.loopplaneDesktop = previousApi;
    }
  });

  it("projects a public-safe main-process failure into the visible diagnostic group", async () => {
    const previousApi = window.loopplaneDesktop;
    let statusHandler: ((event: unknown) => void) | null = null;
    window.loopplaneDesktop = {
      app: {
        status: async () => ({ ready: true }),
        shutdown: async () => ({ ok: true }),
        subscribeStatus: (handler: (event: unknown) => void) => {
          statusHandler = handler;
          return () => {
            statusHandler = null;
          };
        },
      },
    } as never;

    try {
      render(<App transport={stubTransport([])} />);
      act(() => {
        statusHandler?.({
          method: "runtime.state",
          params: {
            state: "failed",
            diagnostic: "The local runtime is incompatible.",
          },
        });
      });
      await waitFor(() =>
        expect(
          screen.getByRole("group", {
            name: "LoopPlane smoke runtime diagnostic",
          }),
        ).toHaveTextContent("The local runtime is incompatible."),
      );
      expect(screen.queryByText(/private|path|exception/i)).toBeNull();
    } finally {
      window.loopplaneDesktop = previousApi;
    }
  });

  it("shows unavailable when transport is missing", () => {
    render(<App transport={null} initialPhase="unavailable" />);
    expect(screen.getByRole("alert").textContent).toMatch(/unavailable/i);
    expect(screen.getByLabelText("LoopPlane smoke prompt")).toBeDisabled();
  });

  it("shows incompatible shell phase", () => {
    render(
      <App
        transport={stubTransport([])}
        initialPhase="incompatible"
      />,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/incompatible/i);
  });

  it("disposes transport on unmount", () => {
    const dispose = vi.fn(async () => undefined);
    const transport = stubTransport([], { dispose });
    const { unmount } = render(<App transport={transport} />);
    unmount();
    expect(dispose).toHaveBeenCalled();
  });

  it("accepts generated shared capability fixtures", () => {
    const mcp: McpConfiguration = generatedCapabilityFixtures.mcp;
    const context: WorkspaceContext = generatedCapabilityFixtures.context;
    const schedule: ManagedSchedule = generatedCapabilityFixtures.schedule;
    const modelDefault: ModelDefault = generatedCapabilityFixtures.model_default;

    expect(mcp.transport).toBe("http");
    expect(context.workspace_label).toBe("docs-repo");
    expect(schedule.name).toBe("daily-notes");
    expect(schedule.instruction).toBe("refresh documentation notes");
    expect(modelDefault.model_id).toBe("model-a");
  });

  it("accepts the generated shared web event fixture", async () => {
    const transport = stubTransport([
      generatedSessionEventFixtures.assistant_output_increment,
      generatedSessionEventFixtures.run_terminated,
    ]);
    render(<App transport={transport} />);
    fireEvent.change(screen.getByLabelText("LoopPlane smoke prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() =>
      expect(screen.getByText("generated hello")).toBeInTheDocument(),
    );
  });
});
