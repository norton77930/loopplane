import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

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
    listModels: async () => [],
    uploadFile: async () => ({ reference: "r", name: "f" }),
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

  it("streams a run and renders markdown, reasoning, and usage", async () => {
    const client = streamingClient([
      { type: "assistant-reasoning-increment", payload: { text: "let me think", turn_index: 0 } },
      { type: "assistant-output-increment", payload: { text: "hi there", turn_index: 0 } },
      {
        type: "turn-completed",
        payload: {
          turn_index: 0,
          stop_reason: "end-turn",
          usage: { input_tokens: 12, output_tokens: 7, cached_tokens: 0, reasoning_tokens: 0 },
        },
      },
      { type: "run-terminated", payload: { reason: "natural-completion", turns_taken: 1 } },
    ]);
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("let me think")).toBeInTheDocument(); // reasoning block
    expect(screen.getByTestId("usage")).toHaveTextContent("12 in"); // usage indicator
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

  it("renders question options and submits the selection", async () => {
    const answerQuestion = vi.fn().mockResolvedValue(undefined);
    const client = streamingClient(
      [{ type: "question-asked", payload: { request_id: "q1", questions: [{ text: "Pick", options: ["A", "B"] }] } }],
      { answerQuestion },
    );
    render(<App client={client} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "go" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const dialog = await screen.findByTestId("question");
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "B" }));
    fireEvent.click(within(dialog).getByText("Send"));
    await waitFor(() => expect(answerQuestion).toHaveBeenCalledWith("s1", "q1", ["B"]));
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

  it("does not submit a prompt until an attached file finishes uploading", async () => {
    let resolveUpload!: (result: { reference: string; name: string }) => void;
    const submit = vi.fn().mockResolvedValue({});
    const client = makeClient({
      submit,
      getAgentControls: vi.fn().mockResolvedValue({
        session_id: "s1",
        permission: {
          default_mode: null,
          selectable_modes: [],
          selection_scope: "run",
          rules_configured: false,
          rule_default: "deny",
          rule_decisions: [],
          plan_entry_available: false,
          plan_exit_requires_approval: true,
          active_run: null,
          last_accepted_run: null,
        },
        budget: {
          pricing: "unavailable",
          session_tracking: "unavailable",
          monthly_tracking: "unavailable",
          run_guard: "unknown",
          session_guard: "unknown",
          monthly_guard: "unknown",
          pre_turn_guard: "disabled",
        },
        actions: ["attach_non_image_upload"],
      }),
      uploadFile: vi.fn().mockReturnValue(
        new Promise<{ reference: string; name: string }>((resolve) => {
          resolveUpload = resolve;
        }),
      ),
    });
    render(<App client={client} />);

    fireEvent.change(screen.getByLabelText("attach files"), {
      target: { files: [new File(["notes"], "notes.txt")] },
    });
    expect(await screen.findByText("uploading")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "summarize" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(submit).not.toHaveBeenCalled();

    await act(async () => {
      resolveUpload({ reference: "upload://notes", name: "notes.txt" });
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith("s1", "summarize", {
        uploads: [{ reference: "upload://notes" }],
      }),
    );
  });

  it("preserves completed upload references when submission fails", async () => {
    const submit = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({});
    const client = makeClient({
      submit,
      getAgentControls: vi.fn().mockResolvedValue({
        session_id: "s1",
        permission: {
          default_mode: null,
          selectable_modes: [],
          selection_scope: "run",
          rules_configured: false,
          rule_default: "deny",
          rule_decisions: [],
          plan_entry_available: false,
          plan_exit_requires_approval: true,
          active_run: null,
          last_accepted_run: null,
        },
        budget: {
          pricing: "unavailable",
          session_tracking: "unavailable",
          monthly_tracking: "unavailable",
          run_guard: "unknown",
          session_guard: "unknown",
          monthly_guard: "unknown",
          pre_turn_guard: "disabled",
        },
        actions: ["attach_non_image_upload"],
      }),
      uploadFile: vi.fn().mockResolvedValue({
        reference: "upload://notes",
        name: "notes.txt",
      }),
    });
    render(<App client={client} />);

    fireEvent.change(screen.getByLabelText("attach files"), {
      target: { files: [new File(["notes"], "notes.txt", { type: "text/plain" })] },
    });
    await screen.findByText("done");
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "summarize" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await screen.findByRole("alert");
    expect(screen.getByText("notes.txt")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "retry" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(submit).toHaveBeenLastCalledWith("s1", "retry", {
        uploads: [{ reference: "upload://notes" }],
      }),
    );
    await waitFor(() => expect(screen.queryByText("notes.txt")).not.toBeInTheDocument());
  });
});
