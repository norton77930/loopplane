import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { SessionTransport } from "../api/transport";
import type { RawEvent } from "../api/types";
import { App } from "../App";

function client(): ApiClient {
  return {
    listSessions: async () => [],
    listModels: async () => [],
    uploadFile: async () => ({ reference: "upload://unused", name: "unused" }),
  } as unknown as ApiClient;
}

describe("App follow-up suggestions", () => {
  it("derives and selects locally, then submits only after an explicit send", async () => {
    let finishRun!: () => void;
    const finished = new Promise<void>((resolve) => {
      finishRun = resolve;
    });
    const submit = vi.fn().mockImplementation(async () => {
      finishRun();
      return {};
    });
    const transport: SessionTransport = {
      mode: "rest_sse",
      openSession: async () => ({ session_id: "s1" }),
      streamSession: async function* (): AsyncGenerator<RawEvent> {
        await finished;
        yield {
          type: "run-terminated",
          payload: { reason: "natural-completion", turns_taken: 1 },
        };
      },
      submit,
      answerApproval: async () => undefined,
      answerQuestion: async () => undefined,
      cancel: async () => undefined,
    };

    render(<App client={client()} transport={transport} />);
    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "first" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const proposal = await screen.findByRole("button", {
      name: "Summarize the result and propose next steps.",
    });
    expect(submit).toHaveBeenCalledTimes(1);
    fireEvent.click(proposal);

    const prompt = screen.getByLabelText("prompt");
    expect(prompt).toHaveValue("Summarize the result and propose next steps.");
    expect(prompt).toHaveFocus();
    expect(submit).toHaveBeenCalledTimes(1);

    fireEvent.change(prompt, {
      target: { value: "Summarize the result and propose next steps, please." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
  });
});
