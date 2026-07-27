import { fireEvent, render, screen } from "@testing-library/react";

import type { AgentControlProjection } from "../api/types";
import { AgentControlsSettings } from "../components/settings/AgentControlsSettings";

const projection: AgentControlProjection = {
  session_id: "session-1",
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
    active_run: { mode: "plan", state: "active", plan_active: true },
    last_accepted_run: {
      mode: "acceptEdits",
      state: "settled",
      plan_active: false,
    },
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

describe("AgentControlsSettings", () => {
  it("shows authoritative posture separately from a draft selection", () => {
    const onPermissionModeChange = vi.fn();
    render(
      <AgentControlsSettings
        projection={projection}
        loading={false}
        failed={false}
        permissionModeDraft="acceptEdits"
        onPermissionModeChange={onPermissionModeChange}
        onRefresh={() => undefined}
      />,
    );

    expect(screen.getByText("Active run").nextSibling).toHaveTextContent("plan");
    expect(screen.getByText("Last accepted run").nextSibling).toHaveTextContent(
      "acceptEdits",
    );
    expect(screen.getByText(/Draft for next run/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /exit plan/i })).toBeNull();

    fireEvent.change(screen.getByLabelText("Permission mode for next run"), {
      target: { value: "plan" },
    });
    expect(onPermissionModeChange).toHaveBeenCalledWith("plan");
  });

  it("keeps posture read only when the host exposes no selectable modes", () => {
    render(
      <AgentControlsSettings
        projection={{
          ...projection,
          permission: { ...projection.permission, selectable_modes: [] },
          actions: [],
        }}
        loading={false}
        failed={false}
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    expect(screen.getByText("No permission changes are available.")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("distinguishes no active session, loading, and unavailable states", () => {
    const { rerender } = render(
      <AgentControlsSettings
        projection={null}
        loading={false}
        failed={false}
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByText("Start or open a session to view agent controls.")).toBeInTheDocument();

    rerender(
      <AgentControlsSettings
        projection={null}
        loading
        failed={false}
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading agent controls");

    rerender(
      <AgentControlsSettings
        projection={null}
        loading={false}
        failed
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Agent controls are unavailable");
  });
});
