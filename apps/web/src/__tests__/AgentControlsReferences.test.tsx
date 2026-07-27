import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import type { AgentControlProjection, WorkspaceContext } from "../api/types";
import { AgentControlsSettings } from "../components/settings/AgentControlsSettings";

const projection: AgentControlProjection = {
  session_id: "session-1",
  permission: {
    default_mode: null,
    selectable_modes: [],
    selection_scope: "run",
    rules_configured: false,
    rule_default: null,
    rule_decisions: [],
    plan_entry_available: false,
    plan_exit_requires_approval: true,
    active_run: null,
    last_accepted_run: null,
  },
  budget: {
    tracking: "unknown",
    pricing: "unknown",
    message_guard: "unknown",
    session_guard: "unknown",
    monthly_guard: "unknown",
    pre_turn_guard: "unknown",
  },
  actions: [],
};

function context(overrides: Partial<WorkspaceContext> = {}): WorkspaceContext {
  return {
    id: "context-1",
    name: "Shared docs",
    description: "must not be rendered",
    workspace_label: "Docs",
    scope: "shared_read_only",
    status: "read_only",
    actions: ["open", "bind"],
    problem: null,
    updated_at: "2026-07-27T00:00:00Z",
    ...overrides,
  };
}

function client(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    listWorkspaceContexts: vi.fn().mockResolvedValue([context()]),
    bindSessionContext: vi.fn().mockResolvedValue({
      session_id: "session-1",
      context_id: "context-1",
      name: "Shared docs",
      workspace_label: "Docs",
      status: "read_only",
    }),
    ...overrides,
  } as unknown as ApiClient;
}

function renderSettings(api: ApiClient, sessionOwned = true) {
  return render(
    <AgentControlsSettings
      client={api}
      sessionId="session-1"
      sessionOwned={sessionOwned}
      sessionContext={{
        context_id: "bound-1",
        context_name: "Current workspace",
        context_workspace_label: "Repo",
        context_status: "active",
      }}
      projection={projection}
      loading={false}
      failed={false}
      permissionModeDraft={null}
      onPermissionModeChange={() => undefined}
      onRefresh={() => undefined}
    />,
  );
}

describe("AgentControlsSettings references", () => {
  it("shows safe current metadata and host-projected bind actions", async () => {
    const api = client();
    const onContextBound = vi.fn();
    render(
      <AgentControlsSettings
        client={api}
        sessionId="session-1"
        sessionOwned
        sessionContext={{
          context_id: "bound-1",
          context_name: "Current workspace",
          context_workspace_label: "Repo",
          context_status: "active",
        }}
        onContextBound={onContextBound}
        projection={projection}
        loading={false}
        failed={false}
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    expect(await screen.findByText("Shared docs")).toBeInTheDocument();
    expect(screen.getByText("Current workspace")).toBeInTheDocument();
    expect(screen.getByText("Repo")).toBeInTheDocument();
    expect(screen.getAllByText("Read only").length).toBeGreaterThan(0);
    expect(screen.queryByText("must not be rendered")).toBeNull();
    expect(screen.queryByText("context-1")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Bind" }));
    await waitFor(() => {
      expect(api.bindSessionContext).toHaveBeenCalledWith("session-1", "context-1");
      expect(onContextBound).toHaveBeenCalledTimes(1);
    });
  });

  it("refreshes stale projected actions and keeps the failure generic", async () => {
    const listWorkspaceContexts = vi
      .fn()
      .mockResolvedValueOnce([context()])
      .mockResolvedValueOnce([]);
    const api = client({
      listWorkspaceContexts,
      bindSessionContext: vi.fn().mockRejectedValue(new Error("private reason")),
    });
    renderSettings(api);

    fireEvent.click(await screen.findByRole("button", { name: "Bind" }));

    expect(await screen.findByText("Workspace binding is unavailable.")).toBeInTheDocument();
    await waitFor(() => expect(listWorkspaceContexts).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("button", { name: "Bind" })).toBeNull();
    expect(screen.queryByText(/private reason/i)).toBeNull();
  });

  it("does not disclose or request context choices without an owned session", () => {
    const api = client();
    renderSettings(api, false);

    expect(screen.queryByText("Current workspace")).toBeNull();
    expect(screen.queryByRole("button", { name: "Bind" })).toBeNull();
    expect(api.listWorkspaceContexts).not.toHaveBeenCalled();
  });
});
