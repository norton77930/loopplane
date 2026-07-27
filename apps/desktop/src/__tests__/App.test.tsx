import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

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
  overrides: Partial<Pick<SidecarTransport, "answerApproval" | "answerQuestion">> = {},
): SidecarTransport {
  return {
    run: async function* () {
      for (const event of events) yield event;
    },
    answerApproval: () => undefined,
    answerQuestion: () => undefined,
    ...overrides,
  } as unknown as SidecarTransport;
}

describe("App (desktop, reusing the unit-018 UI)", () => {
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
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "run it" } });
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
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "ask" } });
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
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
    expect(screen.getByText("hello")).toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() =>
      expect(screen.getByText("generated hello")).toBeInTheDocument(),
    );
  });
});
