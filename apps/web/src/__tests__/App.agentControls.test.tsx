import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { SessionTransport } from "../api/transport";
import type { AgentControlProjection } from "../api/types";
import { App } from "../App";
import { createCapabilitySettingsClient } from "./capabilitySettingsHelpers";

function projection(lastMode: string | null): AgentControlProjection {
  return {
    session_id: "s1",
    permission: {
      default_mode: null,
      selectable_modes: [
        { id: "acceptEdits", kind: "standard", summary: "permission.mode.acceptEdits" },
        { id: "plan", kind: "plan", summary: "permission.mode.plan" },
      ],
      selection_scope: "run",
      rules_configured: true,
      rule_default: "ask",
      rule_decisions: ["deny", "ask", "allow"],
      plan_entry_available: true,
      plan_exit_requires_approval: true,
      active_run: null,
      last_accepted_run: lastMode
        ? { mode: lastMode, state: "settled", plan_active: lastMode === "plan" }
        : null,
    },
    budget: {
      tracking: "unknown",
      pricing: "unknown",
      message_guard: "unknown",
      session_guard: "unknown",
      monthly_guard: "unknown",
      pre_turn_guard: "unknown",
    },
    actions: ["select_permission_mode"],
  };
}

describe("App agent controls", () => {
  it("submits a draft mode only on explicit send and trusts the refreshed posture", async () => {
    let acceptedMode: string | null = null;
    const submit = vi.fn(async (_id: string, _prompt: string, options?: { permissionMode?: string }) => {
      acceptedMode = options?.permissionMode ?? null;
    });
    const transport: SessionTransport = {
      mode: "rest_sse",
      openSession: async () => ({ session_id: "s1" }),
      streamSession: async function* () {
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
    const getAgentControls = vi.fn(async () => projection(acceptedMode));
    const client = {
      ...createCapabilitySettingsClient(),
      getAgentControls,
      listSessions: async () => [],
      history: async () => [],
      inspectSkills: async () => ({ skills: [], problems: [] }),
      inspectTools: async () => [],
    } as unknown as ApiClient;

    render(<App client={client} transport={transport} />);

    fireEvent.change(screen.getByLabelText("prompt"), {
      target: { value: "establish session" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit).toHaveBeenNthCalledWith(1, "s1", "establish session");

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Agent controls" }));
    fireEvent.change(
      await screen.findByLabelText("Permission mode for next run"),
      { target: { value: "plan" } },
    );
    expect(submit).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Draft for next run/)).toHaveTextContent("plan");

    fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
    fireEvent.change(screen.getByLabelText("prompt"), {
      target: { value: "plan this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(submit).toHaveBeenNthCalledWith(2, "s1", "plan this", {
        permissionMode: "plan",
      }),
    );
    await waitFor(() => expect(getAgentControls).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Agent controls" }));
    await waitFor(() =>
      expect(screen.getByText("Last accepted run").nextSibling).toHaveTextContent(
        "plan",
      ),
    );
    expect(screen.queryByText(/Draft for next run/)).toBeNull();
  });
});
