import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { generatedSessionEventFixtures } from "@web/api/generated";
import type { RawEvent } from "@web/api/types";

import { App } from "../App";
import type { SidecarTransport } from "../sidecar";

function stubTransport(events: RawEvent[]): SidecarTransport {
  return {
    run: async function* () {
      for (const event of events) yield event;
    },
    answerApproval: () => undefined,
    answerQuestion: () => undefined,
  } as unknown as SidecarTransport;
}

describe("App (desktop, reusing the unit-018 UI)", () => {
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
